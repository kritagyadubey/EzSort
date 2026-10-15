"""Organizer: folder picker, options, preview table and safe execution."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Optional

from ezsort import engine
from ezsort.gui.pages import Page
from ezsort.gui.theme import configure_tree_tags, row_tag, short_path
from ezsort.gui.widgets import Card, ToolTip, clear_tree, set_tree_columns
from ezsort.watcher import watch_directory

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp


class OrganizerPage(Page):
    def __init__(self, app: "EzSortApp", parent):
        super().__init__(
            app, parent,
            "Organizer",
            "Pick a folder, preview every planned move, then sort with one click.",
        )
        self.preview: Optional[engine.PreviewResult] = None
        self.running = False
        self._item_ops: dict[str, object] = {}
        #: O(1) lookup from source path -> tree item id while a run is in
        #: progress (avoids rescanning the whole table per moved file).
        self._op_items: dict[str, str] = {}
        #: Monotonic id for scans; a result whose id no longer matches has
        #: been superseded and must not touch the table.
        self._scan_seq = 0
        self._build()
        self._seed_from_app()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        body = self.body
        body.columnconfigure(0, weight=1)
        # Page.__init__ gives body row 0 weight=1 (fine for pages that put a
        # single widget there). This page instead needs the *table* row to
        # absorb all extra height, and to be the only row that shrinks in a
        # short window. Leaving row 0 weighted made grid squash the options
        # card - clipping the scan summary in half.
        body.rowconfigure(0, weight=0)
        body.rowconfigure(3, weight=1)

        # -- folder + options card ---------------------------------------
        folder_card = Card(body)
        folder_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        folder_card.columnconfigure(0, weight=1)

        row = ttk.Frame(folder_card, style="Surface.TFrame")
        folder_card.add(row, pady=(4, 0))
        row.columnconfigure(0, weight=1)

        ttk.Label(row, text="Folder", style="Surface.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        entry_row = ttk.Frame(row, style="Surface.TFrame")
        entry_row.grid(row=1, column=0, sticky="ew")
        entry_row.columnconfigure(0, weight=1)

        self.folder_var = tk.StringVar()
        entry = ttk.Entry(entry_row, textvariable=self.folder_var)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        entry.bind("<Return>", lambda e: self.preview_folder())
        ttk.Button(entry_row, text="Browse…", command=self.choose_folder).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(
            entry_row, text="Preview", style="Accent.TButton",
            command=self.preview_folder,
        ).grid(row=0, column=2)

        opts = ttk.Frame(folder_card, style="Surface.TFrame")
        folder_card.add(opts, pady=(12, 0))
        self.recursive_var = tk.BooleanVar(value=bool(self.app.config.get("recursive")))
        self.hidden_var = tk.BooleanVar(
            value=not bool(self.app.config.get("skip_hidden", True))
        )
        ttk.Checkbutton(
            opts, text="Include subfolders", variable=self.recursive_var,
            style="Surface.TCheckbutton", command=self._options_changed,
        ).pack(side="left")
        ttk.Checkbutton(
            opts, text="Include hidden files", variable=self.hidden_var,
            style="Surface.TCheckbutton", command=self._options_changed,
        ).pack(side="left", padx=(16, 0))
        self.partial_var = tk.BooleanVar(
            # Inverted: the checkbox offers to *sort* partial downloads,
            # while the config flag means "skip unfinished downloads".
            value=not bool(self.app.config.get("skip_partial_downloads", True))
        )
        partial_cb = ttk.Checkbutton(
            opts,
            text="Sort unfinished downloads (.crdownload, .part …) too",
            variable=self.partial_var, style="Surface.TCheckbutton",
            command=self._partial_changed,
        )
        partial_cb.pack(side="left", padx=(16, 0))
        ToolTip(
            partial_cb,
            "Off: files that look like a half-finished download are left "
            "alone so they are never sorted mid-download.",
        )

        self.summary_var = tk.StringVar(value="No folder selected.")
        summary = ttk.Label(
            folder_card, textvariable=self.summary_var, style="SurfaceMuted.TLabel"
        )
        folder_card.add(summary, pady=(10, 0))
        ToolTip(summary, lambda: self.summary_var.get())

        # -- toolbar -------------------------------------------------------
        toolbar = ttk.Frame(body, style="TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.sort_btn = ttk.Button(
            toolbar, text="Sort files", style="Accent.TButton",
            command=self.sort_files, state="disabled",
        )
        self.sort_btn.pack(side="left")
        self.cancel_btn = ttk.Button(
            toolbar, text="Cancel", style="Danger.TButton",
            command=self.cancel_run, state="disabled",
        )
        self.cancel_btn.pack(side="left", padx=(10, 0))

        self.watch_btn = ttk.Button(
            toolbar, text="Start watching", style="Small.TButton",
            command=self.toggle_watch,
        )
        self.watch_btn.pack(side="right")
        ttk.Label(
            toolbar, text="Tip: Preview first - nothing moves until you sort.",
            style="Muted.TLabel",
        ).pack(side="right", padx=(0, 14))

        self.progress = ttk.Progressbar(
            body, mode="determinate", maximum=100, style="TProgressbar"
        )
        # only gridded while running

        # -- preview table --------------------------------------------------
        table_card = Card(body, title="Preview of planned moves")
        table_card.grid(row=3, column=0, sticky="nsew", pady=(0, 0))
        table_card.rowconfigure(1, weight=1)
        table_card.columnconfigure(0, weight=1)

        columns = [
            ("File", 240, "w"),
            ("Category", 120, "w"),
            ("Destination", 300, "w"),
            ("Status", 130, "w"),
        ]
        tree_frame = ttk.Frame(table_card, style="Surface.TFrame")
        tree_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 6))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame, columns=[c[0] for c in columns], show="headings",
            selectmode="browse", height=8,
        )
        set_tree_columns(self.tree, columns)
        vsb = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview,
            style="Vertical.TScrollbar",
        )
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        configure_tree_tags(self.tree, self.app.palette)
        self.tree.tag_configure("pending", foreground=self.app.palette["text"])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.detail_var = tk.StringVar(value="Select a row to see full paths.")
        detail = ttk.Label(
            table_card, textvariable=self.detail_var,
            style="SurfaceMuted.TLabel", wraplength=900, justify="left",
        )
        detail.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ToolTip(detail, lambda: self.detail_var.get())

    def _partial_changed(self) -> None:
        # Checkbox offers to *sort* partial downloads; the config flag means
        # "skip unfinished downloads", so the stored value is the inverse.
        self.app.update_config(
            skip_partial_downloads=not bool(self.partial_var.get())
        )
        self._options_changed()

    def _seed_from_app(self) -> None:
        if self.app.folder:
            self.folder_var.set(str(self.app.folder))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def set_folder(self, folder: Path) -> None:
        self.folder_var.set(str(folder))
        # Invalidate any scan that is still in flight for the old folder.
        self._scan_seq += 1
        self.preview = None
        self.sort_btn.state(["disabled"])
        clear_tree(self.tree)
        self.summary_var.set(f"Folder: {short_path(str(folder), 90)}")

    def choose_folder(self) -> None:
        initial = str(self.app.folder) if self.app.folder else str(Path.home())
        chosen = filedialog.askdirectory(
            title="Choose a folder to organize",
            initialdir=initial,
            parent=self.app.root,
        )
        if not chosen:
            return
        folder = Path(chosen).expanduser().resolve()
        self.app.folder = folder
        self.set_folder(folder)
        dash = self.app.pages.get("dashboard")
        if dash is not None:
            dash.folder_var.set(str(folder))
            dash.preview = None
        self.preview_folder()

    def _options_changed(self) -> None:
        # Invalidate an old preview when the options change so the table
        # never shows a stale plan that no longer matches the settings.
        # Never mid-run: the executing plan must stay intact until done.
        if self.running:
            return
        if self.preview is not None:
            self.preview = None
            self.sort_btn.state(["disabled"])
            clear_tree(self.tree)
            self._item_ops.clear()
            self._op_items.clear()
            self.detail_var.set("Select a row to see full paths.")
            self.summary_var.set(
                "Options changed - run Preview again to refresh the plan."
            )
        # A scan started under the old options must not repopulate the
        # table with a plan that no longer matches the settings.
        self._scan_seq += 1

    def _current_options(self) -> dict:
        config = dict(self.app.config)
        config["recursive"] = bool(self.recursive_var.get())
        config["skip_hidden"] = not bool(self.hidden_var.get())
        return config

    def preview_folder(self) -> None:
        raw = self.folder_var.get().strip()
        if not raw:
            self.app.toast("Choose a folder first.", "warning")
            return
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            self.app.toast(f"Not a folder: {folder}", "error")
            return
        folder = folder.resolve()
        self.app.folder = folder
        config = self._current_options()
        recursive = bool(config.get("recursive"))

        self.summary_var.set(f"Scanning {short_path(str(folder), 90)} …")
        self.sort_btn.state(["disabled"])
        # Tag this scan so a result that arrives after the user has already
        # moved on (picked another folder / started another scan) is dropped
        # instead of showing a plan for the wrong folder.
        self._scan_seq += 1
        seq = self._scan_seq

        def work():
            return engine.build_preview(folder, config=config, recursive=recursive)

        def done(preview: engine.PreviewResult):
            if seq != self._scan_seq:
                return  # superseded by a newer scan or a new folder
            self.preview = preview
            self._populate(preview)
            self.app.log({
                "type": "info",
                "message": (
                    f"Preview: {preview.ready} move(s) planned in "
                    f"{short_path(str(folder), 46)}"
                ),
            })
            if preview.errors:
                self.app.toast(
                    f"Scan finished with {len(preview.errors)} warning(s) - "
                    f"see Activity.",
                    "warning",
                )
            elif preview.ready:
                self.app.toast(
                    f"{preview.ready} file(s) ready to sort.", "success"
                )
            else:
                self.app.toast("Everything is already organized.", "success")

        def failed(exc: BaseException):
            if seq != self._scan_seq:
                return  # a newer scan owns the UI now
            self.summary_var.set(f"Scan failed: {exc}")
            self.app.toast(f"Scan failed: {exc}", "error")
            self.app.log({"type": "error", "message": f"Scan failed: {exc}"})

        if not self.app.start_task(
            "scanning", work, on_done=done, on_error=failed
        ):
            # Engine busy - don't leave the summary claiming a scan started.
            self.summary_var.set("Another operation is running - try again shortly.")

    def _populate(self, preview: engine.PreviewResult) -> None:
        clear_tree(self.tree)
        self._item_ops.clear()
        self._op_items.clear()
        folder = preview.folder

        for index, op in enumerate(preview.operations):
            try:
                rel_source = str(op.source.relative_to(folder))
            except ValueError:
                rel_source = op.source.name
            try:
                rel_dest = str(op.destination.relative_to(folder))
            except ValueError:
                rel_dest = str(op.destination)

            status = "Rename (name exists)" if op.collision else "Move"
            tags = list(row_tag(index))
            if op.collision:
                tags.append("rename")
            item = self.tree.insert(
                "", "end",
                values=(rel_source, op.category.split("/")[0], rel_dest, status),
                tags=tuple(tags),
            )
            self._item_ops[item] = op
            self._op_items[str(op.source)] = item

        for index, (path, reason) in enumerate(preview.skipped):
            name = path.name
            try:
                name = str(path.relative_to(folder))
            except ValueError:
                pass
            item = self.tree.insert(
                "", "end",
                values=(name, "-", "-", f"Skipped: {reason}"),
                tags=(*row_tag(len(preview.operations) + index), "skipped"),
            )
            self._item_ops[item] = None

        failed = preview.errors
        lines = [
            f"{len(preview.files)} file(s) scanned",
            f"{preview.ready} move(s) planned",
            f"{len(preview.skipped)} skipped",
        ]
        if failed:
            lines.append(f"{len(failed)} scan warning(s)")
        self.summary_var.set("  |  ".join(lines))
        self.sort_btn.state(["!disabled"] if preview.ready else ["disabled"])

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        op = self._item_ops.get(item)
        if op is None:
            values = self.tree.item(item, "values")
            self.detail_var.set(f"Skipped: {values[0]} - {values[3]}")
            return
        self.detail_var.set(
            f"From: {op.source}\nTo:   {op.destination}"
            + (f"\nRule: {op.reason}" if op.reason else "")
        )

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def sort_files(self) -> None:
        preview = self.preview
        if preview is None or not preview.operations:
            self.app.toast("Run Preview first.", "info")
            return

        total = preview.ready
        if self.app.config.get("confirm_before_move", True):
            lines = self._sample_lines(preview)
            message = (
                f"Move {total} file(s) from\n{preview.folder}\n\n"
                + "\n".join(lines)
                + ("\n…" if total > len(lines) else "")
                + "\n\nExisting files are never overwritten - name clashes "
                  "get a ' (n)' suffix."
            )
            if not messagebox.askyesno(
                "Sort files", message, parent=self.app.root
            ):
                return

        # Capture the folder now: the user may pick a different folder while
        # this run is in progress, and the completion message must describe
        # the run that actually happened.
        run_folder = preview.folder
        self.running = True
        self.sort_btn.state(["disabled"])
        self.cancel_btn.state(["!disabled"])
        self.progress.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.progress.configure(mode="determinate", maximum=total, value=0)

        emit = self.app.runner.emitter(self._on_progress)
        config = self._current_options()

        def progress(done_count, total_count, op):
            emit({"type": "progress", "done": done_count, "total": total_count,
                  "source": str(op.source), "destination": str(op.destination)})

        def work():
            # start_task() creates and registers the "organizing" token
            # before this worker is submitted, so it is always available
            # here. Looking it up (instead of capturing one up front)
            # keeps the cancel button wired to the token this run owns.
            token = self.app.cancel_token_for("organizing")

            def cancel_check() -> bool:
                return bool(token is not None and token.cancelled)

            return engine.run_plan(
                preview,
                dry_run=False,
                progress=progress,
                cancel_check=cancel_check,
                config=config,
            )

        def done(summary: engine.ExecutionSummary):
            self._finish_run(summary, folder=run_folder)

        def failed(exc: BaseException):
            self._finish_run(None, folder=run_folder, error=exc)

        started = self.app.start_task(
            "organizing", work, on_done=done, on_error=failed
        )
        if not started:
            # Another task holds the engine - restore the pre-click state.
            self.running = False
            self.cancel_btn.state(["disabled"])
            self.progress.grid_forget()
            self.sort_btn.state(["!disabled"] if preview.ready else ["disabled"])

    @staticmethod
    def _sample_lines(preview: engine.PreviewResult, limit: int = 8) -> list[str]:
        lines = []
        for op in preview.operations[:limit]:
            lines.append(f"{op.source.name}  ->  {op.destination.parent.name}/")
        return lines

    def _on_progress(self, payload: dict) -> None:
        done = payload.get("done", 0)
        total = payload.get("total", 0)
        try:
            self.progress.configure(value=done)
        except Exception:
            pass
        # Mark the row for the file that just moved (O(1) lookup).
        source = str(payload.get("source", ""))
        item = self._op_items.get(source)
        if item is not None:
            try:
                self.tree.set(item, "Status", "Moved")
                self.tree.item(item, tags=("moved",))
            except Exception:
                pass
        if total:
            self.summary_var.set(f"Moving {done}/{total} …")
        activity = self.app.pages.get("activity")
        if activity is not None:
            activity.set_progress(done, total)

    def _finish_run(self, summary, folder=None,
                    error: Optional[BaseException] = None) -> None:
        self.running = False
        self.sort_btn.state(["!disabled"] if self.preview else ["disabled"])
        self.cancel_btn.state(["disabled"])
        self.progress.grid_forget()
        activity = self.app.pages.get("activity")
        if activity is not None:
            activity.clear_progress()

        if error is not None:
            self.app.toast(f"Sorting failed: {error}", "error")
            self.app.log({"type": "error", "message": f"Sorting failed: {error}"})
            return

        # Mark failures and skipped duplicates in the table (O(1) lookups).
        for result in summary.failures:
            item = self._op_items.get(str(result.operation.source))
            if item is not None:
                try:
                    self.tree.set(item, "Status", "Failed")
                    self.tree.item(item, tags=("failed",))
                except Exception:
                    pass
        for op in summary.skipped_duplicates:
            item = self._op_items.get(str(op.source))
            if item is not None:
                try:
                    self.tree.set(item, "Status", "Skipped (duplicate)")
                    self.tree.item(item, tags=("skipped",))
                except Exception:
                    pass

        message = (
            f"{summary.moved} file(s) organized"
            + (f", {summary.failed} failed" if summary.failed else "")
            + (f"  (batch {summary.batch_id})" if summary.batch_id else "")
        )
        if summary.skipped_duplicates:
            message += f", {len(summary.skipped_duplicates)} duplicate skipped"
        if summary.cancelled:
            message += " - cancelled early"

        self.summary_var.set(message)
        kind = "error" if summary.failed else "success"
        self.app.toast(message, kind)

        self.app.log({
            "type": "moved" if not summary.failed else "failed",
            "message": (
                f"Sorted {summary.moved} file(s) into "
                f"{short_path(str(folder or self.app.folder or ''), 40)}"
                + (f" - {summary.failed} failed" if summary.failed else "")
            ),
        })
        for result in summary.failures[:20]:
            self.app.log({
                "type": "failed",
                "message": f"Failed: {result.operation.source.name} - {result.error}",
            })

        # The plan is spent; ask for a fresh preview.
        self.preview = None
        self.sort_btn.state(["disabled"])
        hist = self.app.pages.get("history")
        if hist is not None:
            hist.schedule_refresh()

    def cancel_run(self) -> None:
        self.app.cancel_current()

    # ------------------------------------------------------------------
    # Watch mode
    # ------------------------------------------------------------------

    def toggle_watch(self) -> None:
        if self.app.watching:
            if self.app._watch_stop is not None:
                self.app._watch_stop.set()
            self.watch_btn.configure(text="Start watching")
            self.app.toast("Stopping watch mode…", "info")
            return

        raw = self.folder_var.get().strip()
        if not raw:
            self.app.toast("Choose a folder to watch first.", "warning")
            return
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            self.app.toast(f"Not a folder: {folder}", "error")
            return
        folder = folder.resolve()
        self.app.folder = folder

        config = self._current_options()
        interval = int(config.get("watch_interval", 2) or 2)
        stop = threading.Event()
        self.app._watch_stop = stop
        self.watch_btn.configure(text="Stop watching")
        emit = self.app.runner.emitter(self._watch_event)

        def work():
            watch_directory(
                folder,
                interval=interval,
                recursive=bool(config.get("recursive")),
                config=config,
                on_event=emit,
                stop_event=stop,
                record_history=True,
                echo=False,  # GUI: never write to stdout (windowed EXE)
            )
            return folder

        def done(_folder):
            self.watch_btn.configure(text="Start watching")
            if self.app._watch_stop is stop:
                self.app._watch_stop = None
            self.app.end_busy("watching")
            self.app.log({"type": "info", "message": "Watch mode stopped."})

        def failed(exc: BaseException):
            self.watch_btn.configure(text="Start watching")
            if self.app._watch_stop is stop:
                self.app._watch_stop = None
            self.app.end_busy("watching")
            self.app.toast(f"Watch mode failed: {exc}", "error")
            self.app.log({"type": "error", "message": f"Watch mode failed: {exc}"})

        self.app.start_task(
            "watching", work, on_done=done, on_error=failed, exclusive=False
        )
        self.app.log({
            "type": "info",
            "message": f"Watching {short_path(str(folder), 50)} for new files…",
        })

    def _watch_event(self, payload: dict) -> None:
        kind = payload.get("type", "info")
        message = payload.get("message", "")
        if kind == "moved":
            self.app.log({"type": "moved", "message": message})
            hist = self.app.pages.get("history")
            if hist is not None:
                hist.schedule_refresh()
        elif kind in ("failed", "error"):
            self.app.log({"type": kind, "message": message})
        elif kind == "detected":
            self.app.log({"type": "info", "message": message})
        # "skipped" stays out of the log to avoid noise, but shows in status.
        if kind == "skipped":
            self.app.toast(message, "info")

    # ------------------------------------------------------------------

    def sync_options_from_config(self) -> None:
        """Refresh the per-run checkboxes from the saved configuration."""
        cfg = self.app.config
        self.recursive_var.set(bool(cfg.get("recursive", False)))
        self.hidden_var.set(not bool(cfg.get("skip_hidden", True)))
        self.partial_var.set(not bool(cfg.get("skip_partial_downloads", True)))

    def on_show(self) -> None:
        if self.app.folder and not self.folder_var.get().strip():
            self.folder_var.set(str(self.app.folder))
        if self.app.watching:
            self.watch_btn.configure(text="Stop watching")
        # Auto-preview when we have a folder but no plan yet.
        if self.app.folder and self.preview is None and not self.app.is_busy():
            self.preview_folder()

    def apply_theme(self) -> None:
        self.tree.tag_configure("failed", foreground=self.app.palette["danger"])
        self.tree.tag_configure("moved", foreground=self.app.palette["success"])
        self.tree.tag_configure("rename", foreground=self.app.palette["warning"])
        super().apply_theme()
