"""Dashboard: folder overview, statistics, distribution and recent activity."""

from __future__ import annotations

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
    ScrollableFrame,
    ToolTip,
)
from ezsort.gui.pages import Page, sp
from ezsort.gui.theme import middle_ellipsis, short_path

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp

KIND_STYLE = {
    "moved": ("SurfaceSuccess.TLabel", "success"),
    "failed": ("SurfaceDanger.TLabel", "danger"),
    "error": ("SurfaceDanger.TLabel", "danger"),
    "cancelled": ("SurfaceWarning.TLabel", "warning"),
    "undone": ("SurfaceInfo.TLabel", "info"),
    "skipped": ("SurfaceWarning.TLabel", "warning"),
    "info": ("SurfaceMuted.TLabel", "muted"),
}


class DashboardPage(Page):
    def __init__(self, app: "EzSortApp", parent):
        super().__init__(
            app, parent,
            "Dashboard",
            "A quick overview of what EzSort sees and what it has done.",
        )
        self.preview: Optional[engine.PreviewResult] = None
        self._build()
        self.header.secondary("Choose folder…", self.choose_folder)
        self.header.secondary("Refresh", self.refresh, style="Ghost.TButton")

    # ------------------------------------------------------------------

    def _build(self) -> None:
        body = self.body
        body.rowconfigure(0, weight=0)
        body.rowconfigure(1, weight=0)
        body.rowconfigure(2, weight=1)
        body.rowconfigure(3, weight=0)

        # Folder row -----------------------------------------------------
        folder_card = Card(body, title="Folder", padding="md")
        folder_card.grid(row=0, column=0, sticky="ew", pady=(0, sp("md")))
        host = folder_card.body

        row = ttk.Frame(host, style="Surface.TFrame")
        row.grid(row=0, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.folder_var = tk.StringVar(value=str(self.app.folder or ""))
        self.folder_entry = ttk.Entry(row, textvariable=self.folder_var)
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, sp("sm")))
        self.folder_entry.bind("<Return>", lambda e: self._apply_folder())
        ttk.Button(row, text="Browse…", style="Secondary.TButton",
                   command=self.choose_folder).grid(row=0, column=1,
                                                   padx=(0, sp("sm")))
        ttk.Button(row, text="Use folder", style="Primary.TButton",
                   command=self._apply_folder).grid(row=0, column=2)

        summary_row = ttk.Frame(host, style="Surface.TFrame")
        summary_row.grid(row=1, column=0, sticky="ew", pady=(sp("sm"), 0))
        summary_row.columnconfigure(0, weight=1)
        self.folder_summary = ttk.Label(
            summary_row, style="SurfaceMuted.TLabel", anchor="w",
            text="No folder selected yet - choose one to begin.",
        )
        self.folder_summary.grid(row=0, column=0, sticky="ew")
        self.folder_badge = Badge(summary_row, "No folder", "muted")
        self.folder_badge.grid(row=0, column=1, sticky="e")
        ToolTip(self.folder_summary, lambda: self.folder_summary.cget("text"))

        # Stat cards ------------------------------------------------------
        stats_row = ttk.Frame(body, style="TFrame")
        stats_row.grid(row=1, column=0, sticky="ew", pady=(0, sp("md")))
        for i in range(4):
            stats_row.columnconfigure(i, weight=1, uniform="stat")

        self.stat_vars: dict[str, tk.StringVar] = {}
        captions = [
            ("scanned", "Files scanned", "Files EzSort can see in the folder"),
            ("ready", "Ready to organize", "Planned moves that can run now"),
            ("categories", "Categories found", "Distinct destinations in the plan"),
            ("organized", "Files organized", "Successful moves recorded in history"),
        ]
        for i, (key, caption, tip) in enumerate(captions):
            card = Card(stats_row, padding="md")
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else sp("sm"), 0))
            var = tk.StringVar(value="—")
            value = ttk.Label(card.body, textvariable=var, style="Stat.TLabel")
            value.grid(row=0, column=0, sticky="w")
            ttk.Label(card.body, text=caption, style="StatCaption.TLabel").grid(
                row=1, column=0, sticky="w", pady=(sp("xxs"), 0))
            self.stat_vars[key] = var
            ToolTip(card, tip)

        # Lower area: distribution + recent activity -----------------------
        lower = ttk.Frame(body, style="TFrame")
        lower.grid(row=2, column=0, sticky="nsew", pady=(0, sp("md")))
        lower.columnconfigure(0, weight=3)
        lower.columnconfigure(1, weight=2)
        lower.rowconfigure(0, weight=1)

        dist_card = Card(lower, title="Category distribution")
        dist_card.grid(row=0, column=0, sticky="nsew", padx=(0, sp("md")))
        dist_card.body.rowconfigure(0, weight=1)
        self.dist_scroll = ScrollableFrame(
            dist_card.body, bg_role="surface", auto_hide=True,
        )
        self.dist_scroll.grid(row=0, column=0, sticky="nsew")
        self.dist_container = self.dist_scroll.body
        self.dist_container.columnconfigure(1, weight=1)
        self._dist_empty = ttk.Label(
            self.dist_container, style="SurfaceMuted.TLabel",
            text="Pick a folder and press Refresh to see the breakdown.",
        )
        self._dist_empty.grid(row=0, column=0, columnspan=3, sticky="w")

        recent_card = Card(lower, title="Recent activity")
        recent_card.grid(row=0, column=1, sticky="nsew")
        recent_card.body.rowconfigure(0, weight=1)
        self.recent_scroll = ScrollableFrame(
            recent_card.body, bg_role="surface", auto_hide=True,
        )
        self.recent_scroll.grid(row=0, column=0, sticky="nsew")
        self.recent_list = self.recent_scroll.body
        self.recent_list.columnconfigure(2, weight=1)
        self._recent_messages: list[ttk.Label] = []
        self.recent_list.bind("<Configure>", self._resize_recent, add="+")
        # Entries stay top-aligned; a trailing spacer row absorbs extra height.
        self.recent_list.rowconfigure(10, weight=1)

        # Quick actions ----------------------------------------------------
        actions = ttk.Frame(body, style="TFrame")
        actions.grid(row=3, column=0, sticky="ew")
        self.preview_btn = ttk.Button(
            actions, text="Preview folder", style="Primary.TButton",
            command=self.preview_folder,
        )
        self.preview_btn.pack(side="left")
        ttk.Button(
            actions, text="Open Organizer", style="Secondary.TButton",
            command=lambda: self.app.show_page("organizer"),
        ).pack(side="left", padx=(sp("sm"), 0))
        self.undo_btn = ttk.Button(
            actions, text="Undo last sort", style="Secondary.TButton",
            command=self.undo_last, state="disabled",
        )
        self.undo_btn.pack(side="left", padx=(sp("sm"), 0))
        ttk.Button(
            actions, text="View history", style="Secondary.TButton",
            command=lambda: self.app.show_page("history"),
        ).pack(side="left", padx=(sp("sm"), 0))

    # ------------------------------------------------------------------

    def sync_folder(self) -> None:
        self.folder_var.set(str(self.app.folder or ""))
        self.folder_badge.set(
            "Folder selected" if self.app.folder else "No folder",
            "neutral" if self.app.folder else "muted")

    def choose_folder(self) -> None:
        import os

        initial = str(self.app.folder) if self.app.folder else os.path.expanduser("~")
        chosen = filedialog.askdirectory(
            title="Choose a folder to organize", initialdir=initial,
            parent=self.app.root,
        )
        if chosen:
            self.folder_var.set(chosen)
            self._apply_folder()

    def _apply_folder(self) -> None:
        raw = self.folder_var.get().strip()
        if not raw:
            self.app.toast("Type or choose a folder first.", "warning")
            return
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            self.app.toast(f"Not a folder: {folder}", "error")
            self.folder_badge.set("Not a folder", "danger")
            return
        folder = folder.resolve()
        self.app.set_folder(folder)
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
        self.folder_badge.set("Scanning…", "info")

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
            self.folder_badge.set("Scan failed", "danger")
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
            self.folder_badge.set("Busy", "warning")

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
        self.folder_badge.set(
            "Ready to sort" if preview.ready else "Already organized",
            "success" if preview.ready else "neutral")

        self.stat_vars["scanned"].set(str(len(preview.files)))
        self.stat_vars["ready"].set(str(len(preview.operations)))
        self.stat_vars["categories"].set(str(len(preview.categories)))

        stats = engine.stats()
        self.stat_vars["organized"].set(str(stats["total_moved"]))
        self._sync_undo_button(bool(engine.load_history()))

        self._render_distribution(preview.categories)
        self.refresh_recent()

    def _render_distribution(self, categories: dict[str, int]) -> None:
        for child in list(self.dist_container.winfo_children()):
            if child is not self._dist_empty:
                child.destroy()
        self._dist_empty.grid_remove()

        if not categories:
            self._dist_empty.grid()
            return

        max_count = max(categories.values()) or 1
        ordered = sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))
        palette = self.app.palette
        row = 0
        for name, count in ordered:
            name_lbl = ttk.Label(
                self.dist_container, text=name, style="SurfaceSmall.TLabel",
            )
            name_lbl.grid(row=row, column=0, sticky="w",
                          pady=(0, sp("xxs")), padx=(0, sp("sm")))

            track = tk.Frame(self.dist_container, bg=palette["surface_alt"],
                             height=tokens.sc(8))
            track.grid(row=row, column=1, sticky="ew", pady=(0, sp("xxs")))
            track.grid_propagate(False)
            fraction = max(0.03, count / max_count)
            fill = tk.Frame(track, bg=palette["accent"], height=tokens.sc(8))
            fill.place(x=0, y=0, relwidth=fraction, relheight=1.0)
            self.register(track, "surface_alt")
            self.register(fill, "accent")

            count_lbl = ttk.Label(
                self.dist_container, text=str(count), style="SurfaceSmall.TLabel",
                width=5, anchor="e",
            )
            count_lbl.grid(row=row, column=2, sticky="e",
                           pady=(0, sp("xxs")), padx=(sp("xs"), sp("md")))
            row += 1

    def refresh_recent(self) -> None:
        for child in list(self.recent_list.winfo_children()):
            child.destroy()
        self._recent_messages = []

        entries = list(reversed(self.app.activity[-4:]))
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
                wraplength=tokens.sc(360), justify="left",
            ).grid(row=0, column=0, columnspan=3, sticky="w")
            return

        for i, entry in enumerate(entries):
            style, kind = KIND_STYLE.get(entry.get("type", "info"),
                                         KIND_STYLE["info"])
            time_text = str(entry.get("time", ""))
            ttk.Label(self.recent_list, text=time_text, width=8, anchor="w",
                      style="SurfaceMicro.TLabel").grid(
                row=i, column=0, sticky="nw", padx=(0, sp("sm")),
                pady=(0, sp("xs")))
            Badge(self.recent_list, kind.capitalize(), kind).grid(
                row=i, column=1, sticky="nw", padx=(0, sp("sm")),
                pady=(0, sp("xs")))
            message = str(entry.get("message", ""))
            lbl = ttk.Label(
                self.recent_list, text=middle_ellipsis(message, 90),
                style=style, justify="left", anchor="w",
                wraplength=tokens.sc(300),
            )
            lbl.grid(row=i, column=2, sticky="nw", pady=(0, sp("xs")))
            self._recent_messages.append(lbl)
            ToolTip(lbl, message)

    def _resize_recent(self, event) -> None:
        """Wrap recent messages to the card width instead of squeezing time."""
        wrap = max(tokens.sc(150), int(event.width) - tokens.sc(150))
        for label in self._recent_messages:
            try:
                label.configure(wraplength=wrap)
            except tk.TclError:  # pragma: no cover - destroyed
                pass

    # ------------------------------------------------------------------

    def _sync_undo_button(self, has_history: bool) -> None:
        self.undo_btn.state(["!disabled"] if has_history else ["disabled"])

    def on_show(self) -> None:
        self.sync_folder()
        stats = engine.stats()
        self.stat_vars["organized"].set(str(stats["total_moved"]))
        self._sync_undo_button(bool(engine.load_history()))
        self.refresh_recent()
        if self.app.folder is None:
            return
        self.folder_var.set(str(self.app.folder))
        if self.preview is None and not self.app.is_busy():
            self.preview_folder()

    def undo_last(self) -> None:
        history = engine.load_history()
        if not history:
            self._sync_undo_button(False)
            self.app.toast("Nothing to undo yet.", "info")
            return
        batch = history[-1]
        if self.app.config.get("confirm_before_move", True):
            dialog = ConfirmDialog(
                self.app, "Undo the last sort?",
                "Files from this sort will move back to where they came from.",
                details=(
                    f"Batch {batch.get('batch_id')}: "
                    f"{batch.get('total_moved', 0)} file(s)\n"
                    f"Folder: {batch.get('folder', '(not recorded)')}\n\n"
                    "Nothing at the original location is ever overwritten."
                ),
                confirm_label="Undo this sort",
            )
            if not dialog.show():
                return
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
            self._sync_undo_button(bool(engine.load_history()))
            if self.app.current_page == "dashboard":
                self.preview_folder()

        self.app.start_task("undo", work, on_done=done)

    def refresh(self) -> None:
        self.preview = None
        self.preview_folder()

    def apply_theme(self) -> None:
        if self.preview is not None:
            self._render_distribution(self.preview.categories)
        super().apply_theme()
