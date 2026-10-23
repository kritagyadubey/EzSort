"""Organizer: folder picker, options, preview table and safe execution."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Optional

from ezsort import engine
from ezsort.gui import tokens
from ezsort.gui.components import (
    Badge,
    Card,
    ConfirmDialog,
    SearchBox,
    Table,
    ToolTip,
)
from ezsort.gui.pages import Page, sp
from ezsort.gui.theme import middle_ellipsis, row_tag, short_path
from ezsort.watcher import watch_directory

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp

FILTERS = [
    ("all", "All rows"),
    ("moves", "Moves"),
    ("renames", "Renames"),
    ("skipped", "Skipped"),
]


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
        self._row_order: list[str] = []
        self._row_meta: dict[str, tuple[str, str]] = {}
        self._build()
        self._seed_from_app()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        body = self.body
        body.columnconfigure(0, weight=1)
        # Only the table row absorbs extra height; the folder card and
        # toolbar keep their natural height even in a short window.
        body.rowconfigure(0, weight=0)
        body.rowconfigure(1, weight=0)
        body.rowconfigure(2, weight=0)
        body.rowconfigure(3, weight=1)

        # -- folder + options card ---------------------------------------
        folder_card = Card(body)
        folder_card.grid(row=0, column=0, sticky="ew", pady=(0, sp("md")))
        host = folder_card.body

        head = ttk.Frame(host, style="Surface.TFrame")
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Folder to organize", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w")
        self.folder_badge = Badge(head, "No folder", "muted")
        self.folder_badge.grid(row=0, column=1, sticky="e")

        entry_row = ttk.Frame(host, style="Surface.TFrame")
        entry_row.grid(row=1, column=0, sticky="ew", pady=(sp("sm"), 0))
        entry_row.columnconfigure(0, weight=1)
        self.folder_var = tk.StringVar()
        self.folder_entry = ttk.Entry(entry_row, textvariable=self.folder_var)
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, sp("sm")))
        self.folder_entry.bind("<Return>", lambda e: self.preview_folder())
        ttk.Button(entry_row, text="Browse…", style="Secondary.TButton",
                   command=self.choose_folder).grid(row=0, column=1,
                                                   padx=(0, sp("sm")))
        ttk.Button(entry_row, text="Open", style="Secondary.TButton",
                   command=self.open_folder).grid(row=0, column=2,
                                                  padx=(0, sp("sm")))
        ttk.Button(entry_row, text="Preview", style="Primary.TButton",
                   command=self.preview_folder).grid(row=0, column=3)

        opts = ttk.Frame(host, style="Surface.TFrame")
        opts.grid(row=2, column=0, sticky="w", pady=(sp("md"), 0))
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
        ).pack(side="left", padx=(sp("lg"), 0))
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
        partial_cb.pack(side="left", padx=(sp("lg"), 0))
        ToolTip(
            partial_cb,
            "Off: files that look like a half-finished download are left "
            "alone so they are never sorted mid-download.",
        )

        summary_row = ttk.Frame(host, style="Surface.TFrame")
        summary_row.grid(row=3, column=0, sticky="ew", pady=(sp("md"), 0))
        summary_row.columnconfigure(0, weight=1)
        self.summary_var = tk.StringVar(value="No folder selected.")
        self.summary = ttk.Label(
            summary_row, textvariable=self.summary_var,
            style="SurfaceMuted.TLabel", anchor="w",
        )
        self.summary.grid(row=0, column=0, sticky="ew")
        ToolTip(self.summary, lambda: self.summary_var.get())

        # -- toolbar ------------------------------------------------------
        toolbar = ttk.Frame(body, style="TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, sp("sm")))
        toolbar.columnconfigure(3, weight=1)

        self.sort_btn = ttk.Button(
            toolbar, text="Sort files", style="Primary.TButton",
            command=self.sort_files, state="disabled",
        )
        self.sort_btn.grid(row=0, column=0, sticky="w")
        self.cancel_btn = ttk.Button(
            toolbar, text="Cancel", style="Danger.TButton",
            command=self.cancel_run, state="disabled",
        )
        self.cancel_btn.grid(row=0, column=1, padx=(sp("sm"), 0), sticky="w")

        self.filter_var = tk.StringVar(value=FILTERS[0][0])
        self.filter_box = ttk.Combobox(
            toolbar, textvariable=self.filter_var, state="readonly",
            values=[label for _key, label in FILTERS], width=12,
        )
        self.filter_box.grid(row=0, column=2, sticky="e", padx=(sp("sm"), 0))
        self.filter_box.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        self.search = SearchBox(
            toolbar, placeholder="Search files…", width=28,
            on_change=lambda _text: self._apply_filter(),
        )
        self.search.grid(row=0, column=3, sticky="e", padx=(sp("sm"), 0))

        self.watch_btn = ttk.Button(
            toolbar, text="Start watching", style="Secondary.TButton",
            command=self.toggle_watch,
        )
        self.watch_btn.grid(row=0, column=4, padx=(sp("sm"), 0))

        # -- progress -----------------------------------------------------
        self.progress_frame = ttk.Frame(body, style="TFrame")
        self.progress_frame.grid(row=2, column=0, sticky="ew", pady=(0, sp("sm")))
        self.progress_frame.columnconfigure(0, weight=1)
        self.progress_var = tk.StringVar(value="")
        ttk.Label(self.progress_frame, textvariable=self.progress_var,
                  style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(
            self.progress_frame, mode="determinate", maximum=100,
            style="TProgressbar",
        )
        self.progress.grid(row=1, column=0, sticky="ew", pady=(sp("xs"), 0))
        self.progress_frame.grid_remove()

        # -- preview table -------------------------------------------------
        table_card = Card(body, title="Preview of planned moves")
        table_card.grid(row=3, column=0, sticky="nsew")
        table_card.body.rowconfigure(0, weight=1)
        self.table_badge = Badge(table_card.header, "No preview", "muted")
        self.table_badge.grid(row=0, column=1, sticky="e")

        self.table = Table(
            table_card.body,
            columns=[
                ("File", "File", 250, "w"),
                ("Category", "Category", 130, "w"),
                ("Destination", "Destination", 300, "w"),
                ("Status", "Status", 150, "w"),
            ],
            height=9,
            on_select=self._on_select,
            empty_text=("Choose a folder and press Preview.\n"
                        "Nothing is moved until you press Sort files."),
        )
        self.table.grid(row=0, column=0, sticky="nsew")
        self.tree = self.table.tree

        self.detail_var = tk.StringVar(value="Select a row to see the full paths.")
        detail = ttk.Label(
            table_card.body, textvariable=self.detail_var,
            style="SurfaceMuted.TLabel", justify="left", anchor="w",
        )
        detail.grid(row=1, column=0, sticky="ew", pady=(sp("sm"), 0))
        ToolTip(detail, lambda: self.detail_var.get())

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    def _partial_changed(self) -> None:
        # Checkbox offers to *sort* partial downloads; the config flag means
        # "skip unfinished downloads", so the stored value is the inverse.
        self.app.update_config(
            skip_partial_downloads=not bool(self.partial_var.get()),
            quiet=True,
        )
        self._options_changed()

    def _seed_from_app(self) -> None:
        if self.app.folder:
            self.folder_var.set(str(self.app.folder))
            self.folder_badge.set("Folder selected", "neutral")

    def focus_search(self) -> None:
        self.search.focus_entry()

    def escape(self) -> None:
        if self.search.value():
            self.search.clear()

    def sync_folder(self) -> None:
        if self.app.folder and self.app.folder != Path(self.folder_var.get().strip() or "."):
            self.folder_var.set(str(self.app.folder))
        self._sync_folder_badge()

    def _sync_folder_badge(self) -> None:
        raw = self.folder_var.get().strip()
        if not raw:
            self.folder_badge.set("No folder", "muted")
        elif Path(raw).expanduser().is_dir():
            self.folder_badge.set("Folder ready", "neutral")
        else:
            self.folder_badge.set("Not a folder", "danger")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def set_folder(self, folder: Path) -> None:
        self.folder_var.set(str(folder))
        # Invalidate any scan that is still in flight for the old folder.
        self._scan_seq += 1
        self.preview = None
        self.sort_btn.state(["disabled"])
        self._clear_table()
        self.summary_var.set(f"Folder: {short_path(str(folder), 90)}")
        self.folder_badge.set("Folder ready", "neutral")
        self.table_badge.set("No preview", "muted")

    def open_folder(self) -> None:
        raw = self.folder_var.get().strip()
        if not raw:
            self.app.toast("Choose a folder first.", "warning")
            return
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            self.app.toast(f"Not a folder: {folder}", "error")
            return
        try:
            os.startfile(str(folder))  # noqa: S606 - user-requested open
        except Exception as e:  # pragma: no cover - shell integration
            self.app.toast(f"Could not open the folder: {e}", "error")

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
        self.app.set_folder(folder)
        self.set_folder(folder)
        dash = self.app.pages.get("dashboard")
        if dash is not None:
            dash.sync_folder()
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
            self._clear_table()
            self.detail_var.set("Select a row to see the full paths.")
            self.summary_var.set(
                "Options changed - run Preview again to refresh the plan."
            )
            self.table_badge.set("Preview stale", "warning")
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
            self.folder_badge.set("Not a folder", "danger")
            return
        folder = folder.resolve()
        self.app.set_folder(folder)
        config = self._current_options()
        recursive = bool(config.get("recursive"))

        self.summary_var.set(f"Scanning {short_path(str(folder), 90)} …")
        self.folder_badge.set("Scanning…", "info")
        self.table_badge.set("Scanning…", "info")
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
            self.folder_badge.set("Scan failed", "danger")
            self.table_badge.set("No preview", "muted")
            self.app.toast(f"Scan failed: {exc}", "error")
            self.app.log({"type": "error", "message": f"Scan failed: {exc}"})

        if not self.app.start_task(
            "scanning", work, on_done=done, on_error=failed
        ):
            # Engine busy - don't leave the summary claiming a scan started.
            self.summary_var.set("Another operation is running - try again shortly.")
            self.folder_badge.set("Busy", "warning")
            self.table_badge.set("Busy", "warning")

    def _clear_table(self) -> None:
        self.table.clear()
        self._item_ops.clear()
        self._op_items.clear()
        self._row_order.clear()
        self._row_meta.clear()

    def _populate(self, preview: engine.PreviewResult) -> None:
        self._clear_table()
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
            kind = "renames" if op.collision else "moves"
            if op.collision:
                tags.append("rename")
            item = self.table.insert_row(
                (middle_ellipsis(rel_source, 56),
                 middle_ellipsis(op.category.split("/")[0], 28),
                 middle_ellipsis(rel_dest, 72),
                 status),
                tags=tags,
                cell_text={"File": str(op.source),
                           "Destination": str(op.destination)},
            )
            self._item_ops[item] = op
            self._op_items[str(op.source)] = item
            self._row_order.append(item)
            self._row_meta[item] = (f"{rel_source} {op.category} {rel_dest}".lower(),
                                    kind)

        for index, (path, reason) in enumerate(preview.skipped):
            name = path.name
            try:
                name = str(path.relative_to(folder))
            except ValueError:
                pass
            item = self.table.insert_row(
                (middle_ellipsis(name, 56), "-", "-",
                 middle_ellipsis(f"Skipped: {reason}", 40)),
                tags=(*row_tag(len(preview.operations) + index), "skipped"),
                cell_text={"File": str(path), "Status": reason},
            )
            self._item_ops[item] = None
            self._row_order.append(item)
            self._row_meta[item] = (f"{name} skipped {reason}".lower(), "skipped")

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
        self.folder_badge.set(
            "Ready to sort" if preview.ready else "Already organized",
            "success" if preview.ready else "neutral",
        )
        self.table_badge.set(
            f"{preview.ready} move(s)" if preview.ready else "Nothing to move",
            "accent" if preview.ready else "muted",
        )
        self._apply_filter()

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

    # -- search / filter ------------------------------------------------

    def _selected_filter(self) -> str:
        label = self.filter_var.get()
        return next((key for key, text in FILTERS if text == label), "all")

    def _apply_filter(self) -> None:
        query = self.search.value().lower()
        kind = self._selected_filter()
        visible = 0
        for item in self._row_order:
            text, row_kind = self._row_meta.get(item, ("", ""))
            match = (kind == "all" or row_kind == kind) and (
                not query or query in text)
            if match:
                try:
                    self.tree.reattach(item, "", "end")
                except tk.TclError:
                    pass
                visible += 1
            else:
                try:
                    self.tree.detach(item)
                except tk.TclError:
                    pass
        if self._row_order:
            self.table_badge.set(
                f"{visible} of {len(self._row_order)} row(s)"
                if visible != len(self._row_order) else f"{visible} row(s)",
                "accent" if visible else "muted",
            )
        self.table.set_empty(
            "No rows match this search or filter."
            if self._row_order else
            "Choose a folder and press Preview.\n"
            "Nothing is moved until you press Sort files."
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
            details = (
                f"{total} file(s) will move into subfolders of\n"
                f"{preview.folder}\n\n"
                + "\n".join(lines)
                + ("\n…" if total > len(lines) else "")
                + "\n\nExisting files are never overwritten - name clashes "
                  "get a ' (n)' suffix."
            )
            dialog = ConfirmDialog(
                self.app, "Sort these files?",
                "This is the plan you previewed. Nothing else will move.",
                details=details,
                confirm_label=f"Sort {total} file(s)",
            )
            if not dialog.show():
                return

        # Capture the folder now: the user may pick a different folder while
        # this run is in progress, and the completion message must describe
        # the run that actually happened.
        run_folder = preview.folder
        self.running = True
        self.sort_btn.state(["disabled"])
        self.cancel_btn.state(["!disabled"])
        self.progress_frame.grid()
        self.progress.configure(mode="determinate", maximum=max(1, total),
                                value=0)
        self.progress_var.set(f"Moving 0 of {total} file(s)…")
        self.table_badge.set("Sorting…", "info")

        emit = self.app.runner.emitter(self._on_progress)
        config = self._current_options()

        def progress(done_count, total_count, op):
            emit({"type": "progress", "done": done_count,
                  "total": total_count,
                  "source": str(op.source),
                  "destination": str(op.destination)})

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
            self.progress_frame.grid_remove()
            self.sort_btn.state(["!disabled"] if preview.ready else ["disabled"])
            self.table_badge.set(f"{preview.ready} move(s)", "accent")

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
                self.table.update_row(
                    item,
                    (*self.tree.item(item, "values")[:3], "Moved"),
                    tags=("moved",),
                )
                self._row_meta[item] = (
                    self._row_meta.get(item, ("", "moves"))[0], "moved")
            except Exception:
                pass
        if total:
            self.progress_var.set(f"Moving {done} of {total} file(s)…")
            self.summary_var.set(f"Moving {done}/{total} …")
        activity = self.app.pages.get("activity")
        if activity is not None:
            activity.set_progress(done, total)

    def _finish_run(self, summary, folder=None,
                    error: Optional[BaseException] = None) -> None:
        self.running = False
        self.cancel_btn.state(["disabled"])
        self.progress_frame.grid_remove()
        activity = self.app.pages.get("activity")
        if activity is not None:
            activity.clear_progress()

        if error is not None:
            self.sort_btn.state(["!disabled"] if self.preview else ["disabled"])
            self.app.toast(f"Sorting failed: {error}", "error")
            self.app.log({"type": "error", "message": f"Sorting failed: {error}"})
            self.table_badge.set("Run failed", "danger")
            return

        # Mark failures and skipped duplicates in the table (O(1) lookups).
        for result in summary.failures:
            item = self._op_items.get(str(result.operation.source))
            if item is not None:
                try:
                    self.table.update_row(
                        item,
                        (*self.tree.item(item, "values")[:3], "Failed"),
                        tags=("failed",),
                    )
                except Exception:
                    pass
        for op in summary.skipped_duplicates:
            item = self._op_items.get(str(op.source))
            if item is not None:
                try:
                    self.table.update_row(
                        item,
                        (*self.tree.item(item, "values")[:3],
                         "Skipped (duplicate)"),
                        tags=("skipped",),
                    )
                except Exception:
                    pass

        message = f"{summary.moved} file(s) organized"
        if summary.failed:
            message += f", {summary.failed} failed"
        if summary.skipped_duplicates:
            message += f", {len(summary.skipped_duplicates)} duplicate skipped"
        if summary.cancelled:
            message += " - cancelled early"
        if summary.batch_id:
            message += f"  (batch {summary.batch_id})"

        self.summary_var.set(message)
        kind = "error" if summary.failed else (
            "warning" if summary.cancelled else "success")
        self.app.toast(message, kind)
        self.table_badge.set(
            "Cancelled" if summary.cancelled else
            ("Finished with errors" if summary.failed else "Finished"),
            "warning" if summary.cancelled else
            ("danger" if summary.failed else "success"),
        )

        log_kind = "cancelled" if summary.cancelled else (
            "failed" if summary.failed else "moved")
        self.app.log({
            "type": log_kind,
            "message": (
                f"Sorted {summary.moved} file(s) into "
                f"{short_path(str(folder or self.app.folder or ''), 40)}"
                + (f" - {summary.failed} failed" if summary.failed else "")
                + (" (cancelled)" if summary.cancelled else "")
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
        self.app.set_folder(folder)

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
        self._sync_folder_badge()
        if self.app.watching:
            self.watch_btn.configure(text="Stop watching")
        else:
            self.watch_btn.configure(text="Start watching")
        # Auto-preview when we have a folder but no plan yet.
        if self.app.folder and self.preview is None and not self.app.is_busy():
            self.preview_folder()

    def apply_theme(self) -> None:
        self.table.apply_theme(self.app.palette)
        super().apply_theme()
