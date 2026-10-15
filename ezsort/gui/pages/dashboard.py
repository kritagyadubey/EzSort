"""Dashboard: folder overview, statistics, distribution and recent activity."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Optional

from ezsort import engine
from ezsort.gui.pages import Page
from ezsort.gui.theme import short_path
from ezsort.gui.widgets import Card, ToolTip

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp


class DashboardPage(Page):
    def __init__(self, app: "EzSortApp", parent):
        super().__init__(
            app, parent,
            "Dashboard",
            "A quick overview of what EzSort sees and what it has done.",
        )
        self.preview: Optional[engine.PreviewResult] = None
        self._build()
        self.header.action_button("Choose folder…", self.choose_folder)
        self.header.action_button("Refresh", self.refresh)

    # ------------------------------------------------------------------

    def _build(self) -> None:
        outer = ttk.Frame(self.body, style="TFrame")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        # Folder row -----------------------------------------------------
        folder_card = Card(outer)
        folder_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        folder_card.columnconfigure(0, weight=1)

        row = ttk.Frame(folder_card, style="Surface.TFrame")
        folder_card.add(row, pady=(4, 0))
        row.columnconfigure(0, weight=1)

        self.folder_var = tk.StringVar(value=str(self.app.folder or ""))
        entry = ttk.Entry(row, textvariable=self.folder_var, style="TEntry")
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        entry.bind("<Return>", lambda e: self._apply_folder())
        self.register(entry, "surface")
        ttk.Button(row, text="Browse…", command=self.choose_folder).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(
            row, text="Use folder", style="Accent.TButton",
            command=self._apply_folder,
        ).grid(row=0, column=2)

        self.folder_summary = ttk.Label(
            folder_card, style="SurfaceMuted.TLabel",
            text="No folder selected yet - choose one to begin.",
        )
        folder_card.add(self.folder_summary, pady=(10, 0))

        # Stat cards ------------------------------------------------------
        stats_row = ttk.Frame(outer, style="TFrame")
        stats_row.grid(row=1, column=0, sticky="new", pady=(0, 14))
        for i in range(4):
            stats_row.columnconfigure(i, weight=1, uniform="stat")

        self.stat_vars = {}
        captions = [
            ("scanned", "Files scanned"),
            ("ready", "Ready to organize"),
            ("categories", "Categories found"),
            ("last_run", "Files organized (all time)"),
        ]
        for i, (key, caption) in enumerate(captions):
            card = Card(stats_row)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            value = ttk.Label(card, text="—", style="Stat.TLabel")
            card.add(value, pady=(2, 0))
            label = ttk.Label(card, text=caption, style="StatCaption.TLabel")
            card.add(label, pady=(2, 0))
            self.stat_vars[key] = value

        # Lower area: distribution + recent activity -----------------------
        lower = ttk.Frame(outer, style="TFrame")
        lower.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        outer.rowconfigure(2, weight=1)
        lower.columnconfigure(0, weight=3)
        lower.columnconfigure(1, weight=2)

        # Distribution
        dist_card = Card(lower, title="Category distribution")
        dist_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 14))
        dist_card.columnconfigure(1, weight=1)
        self.dist_container = ttk.Frame(dist_card, style="Surface.TFrame")
        self.dist_container.grid(row=dist_card.next_row, column=0, sticky="nsew")
        self.dist_container.columnconfigure(1, weight=1)
        self._dist_rows: list[tuple[str, ttk.Label, ttk.Label, ttk.Frame]] = []
        ttk.Label(
            self.dist_container, style="SurfaceMuted.TLabel",
            text="Pick a folder and hit Refresh to see the breakdown.",
        ).grid(row=0, column=0, columnspan=4, sticky="w")

        # Recent activity
        recent_card = Card(lower, title="Recent activity")
        recent_card.grid(row=0, column=1, sticky="nsew", pady=(0, 14))
        recent_card.columnconfigure(0, weight=1)
        self.recent_list = ttk.Frame(recent_card, style="Surface.TFrame")
        recent_card.add(self.recent_list, pady=(4, 0))
        self.recent_list.columnconfigure(0, weight=1)
        ttk.Label(
            self.recent_list, style="SurfaceMuted.TLabel",
            text="Actions taken in this session and past sorts appear here.",
        ).grid(row=0, column=0, sticky="w")

        # Quick actions ----------------------------------------------------
        actions = ttk.Frame(outer, style="TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(0, 2))
        self.preview_btn = ttk.Button(
            actions, text="Preview folder", style="Accent.TButton",
            command=self.preview_folder,
        )
        self.preview_btn.pack(side="left")
        ttk.Button(
            actions, text="Open Organizer", style="Small.TButton",
            command=lambda: self.app.show_page("organizer"),
        ).pack(side="left", padx=(10, 0))
        ttk.Button(
            actions, text="Undo last sort", style="Small.TButton",
            command=self.undo_last,
        ).pack(side="left", padx=(10, 0))
        ttk.Button(
            actions, text="View history", style="Small.TButton",
            command=lambda: self.app.show_page("history"),
        ).pack(side="left", padx=(10, 0))

    # ------------------------------------------------------------------

    def choose_folder(self) -> None:
        import os

        initial = str(self.app.folder) if self.app.folder else os.path.expanduser("~")
        chosen = filedialog.askdirectory(
            title="Choose a folder to organize", initialdir=initial, parent=self.app.root
        )
        if chosen:
            self.folder_var.set(chosen)
            self._apply_folder()

    def _apply_folder(self) -> None:
        raw = self.folder_var.get().strip()
        if not raw:
            self.app.toast("Type or choose a folder first.", "warning")
            return
        from pathlib import Path

        folder = Path(raw).expanduser()
        if not folder.is_dir():
            self.app.toast(f"Not a folder: {folder}", "error")
            return
        self.app.folder = folder.resolve()
        self.app.log({"type": "info", "message": f"Selected folder {folder}"})
        self.app.toast(f"Folder set: {short_path(str(folder), 60)}", "success")
        org = self.app.pages.get("organizer")
        if org is not None:
            org.set_folder(folder)
        self.preview = None
        self.preview_folder()

    def preview_folder(self) -> None:
        folder = self.app.folder
        if folder is None:
            self.app.toast("Choose a folder first.", "warning")
            return
        self.preview_btn.state(["disabled"])
        self.folder_summary.configure(text=f"Scanning {short_path(str(folder), 80)} …")

        config = dict(self.app.config)
        recursive = bool(config.get("recursive", False))

        def work():
            return engine.build_preview(folder, config=config, recursive=recursive)

        def done(preview: engine.PreviewResult):
            self.preview = preview
            self.preview_btn.state(["!disabled"])
            self._render(preview)
            self.app.log({
                "type": "info",
                "message": (
                    f"Scanned {short_path(str(folder), 60)}: "
                    f"{len(preview.files)} files, {len(preview.operations)} ready"
                ),
            })
            if not preview.errors:
                self.app.toast(
                    f"{len(preview.files)} files scanned - "
                    f"{len(preview.operations)} ready to organize.",
                    "success",
                )
            else:
                self.app.toast(
                    f"Scan finished with {len(preview.errors)} warning(s).",
                    "warning",
                )

        def failed(exc: BaseException):
            self.preview_btn.state(["!disabled"])
            self.folder_summary.configure(text=f"Scan failed: {exc}")
            self.app.toast(f"Scan failed: {exc}", "error")
            self.app.log({"type": "error", "message": f"Scan failed: {exc}"})

        if not self.app.start_task(
            "scanning", work, on_done=done, on_error=failed
        ):
            # Engine busy - undo the optimistic "Scanning …" text.
            self.preview_btn.state(["!disabled"])
            self.folder_summary.configure(
                text="Another operation is running - try again shortly."
            )

    def _render(self, preview: engine.PreviewResult) -> None:
        folder = preview.folder
        parts = [f"Folder: {short_path(str(folder), 58)}"]
        parts.append(f"{len(preview.files)} file(s)")
        if preview.total_size:
            from ezsort.utils import format_size

            parts.append(format_size(preview.total_size))
        if preview.skipped:
            parts.append(f"{len(preview.skipped)} skipped")
        self.folder_summary.configure(text="  |  ".join(parts))
        ToolTip(self.folder_summary, lambda: str(folder))

        self.stat_vars["scanned"].configure(text=str(len(preview.files)))
        self.stat_vars["ready"].configure(text=str(len(preview.operations)))
        self.stat_vars["categories"].configure(text=str(len(preview.categories)))

        # Last-run number from history
        stats = engine.stats()
        self.stat_vars["last_run"].configure(text=str(stats["total_moved"]))

        self._render_distribution(preview.categories)
        self.refresh_recent()

    def _render_distribution(self, categories: dict[str, int]) -> None:
        for row in self.dist_container.winfo_children():
            row.destroy()
        self._dist_rows.clear()

        if not categories:
            ttk.Label(
                self.dist_container, style="SurfaceMuted.TLabel",
                text="No files to show yet.",
            ).grid(row=0, column=0, columnspan=4, sticky="w")
            return

        max_count = max(categories.values()) or 1
        ordered = sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))
        palette = self.app.palette

        for i, (name, count) in enumerate(ordered, start=1):
            name_lbl = ttk.Label(
                self.dist_container, text=name, style="Surface.TLabel", width=14
            )
            name_lbl.grid(row=i, column=0, sticky="w", pady=3, padx=(0, 8))

            track = tk.Frame(
                self.dist_container, bg=palette["surface_alt"], height=9
            )
            track.grid(row=i, column=1, sticky="ew", pady=3)
            track.grid_propagate(False)
            fraction = max(0.03, count / max_count)
            fill = tk.Frame(track, bg=palette["accent"], height=9)
            fill.place(x=0, y=0, relwidth=fraction, relheight=1.0)
            self.register(track, "surface_alt")

            count_lbl = ttk.Label(
                self.dist_container, text=str(count), style="Surface.TLabel",
                width=5, anchor="e",
            )
            count_lbl.grid(row=i, column=2, sticky="e", pady=3)

    def refresh_recent(self) -> None:
        for child in self.recent_list.winfo_children():
            child.destroy()

        entries = list(reversed(self.app.activity[-6:]))
        if not entries:
            # Fall back to persisted history batches.
            history = engine.load_history()
            entries = [
                {
                    "type": "moved",
                    "message": (
                        f"Batch {b['batch_id']}: {b.get('total_moved', 0)} file(s) "
                        f"organized"
                    ),
                    "time": str(b.get("timestamp", ""))[:19].replace("T", " "),
                }
                for b in reversed(history[-4:])
            ]

        if not entries:
            ttk.Label(
                self.recent_list, style="SurfaceMuted.TLabel",
                text="Nothing yet - organize a folder to get started.",
            ).grid(row=0, column=0, sticky="w")
            return

        palette = self.app.palette
        color_map = {
            "moved": palette["success"],
            "failed": palette["danger"],
            "error": palette["danger"],
            "info": palette["muted"],
            "skipped": palette["warning"],
            "undone": palette["accent"],
        }
        for i, entry in enumerate(entries):
            text = f"{entry.get('time', '')}  {entry.get('message', '')}"
            lbl = tk.Label(
                self.recent_list,
                text=text[:80] + ("…" if len(text) > 80 else ""),
                bg=palette["surface"],
                fg=color_map.get(entry.get("type", "info"), palette["text"]),
                font=("Segoe UI", 9),
                anchor="w",
                justify="left",
            )
            lbl.grid(row=i, column=0, sticky="w", pady=2)
            self.register(lbl, "surface")
            ToolTip(lbl, text)

    # ------------------------------------------------------------------

    def on_show(self) -> None:
        if self.app.folder is None:
            self.folder_var.set("")
            return
        self.folder_var.set(str(self.app.folder))
        if self.preview is None:
            self.preview_folder()
        else:
            stats = engine.stats()
            self.stat_vars["last_run"].configure(text=str(stats["total_moved"]))
            self.refresh_recent()

    def undo_last(self) -> None:
        history = engine.load_history()
        if not history:
            self.app.toast("Nothing to undo yet.", "info")
            return
        if not self.app.config.get("confirm_before_move", True):
            self._do_undo()
            return
        if messagebox.askyesno(
            "Undo last sort",
            "Restore the files from the most recent sort to their original "
            "locations?",
            parent=self.app.root,
        ):
            self._do_undo()

    def _do_undo(self) -> None:
        def work():
            return engine.undo_last_batch()

        def done(result):
            success, message = result
            self.app.log({
                "type": "undone" if success else "failed",
                "message": message,
            })
            self.app.toast(message, "success" if success else "error")
            self.preview = None
            if self.app.current_page == "dashboard":
                self.preview_folder()

        self.app.start_task("undo", work, on_done=done)

    def refresh(self) -> None:
        self.preview = None
        self.preview_folder()
