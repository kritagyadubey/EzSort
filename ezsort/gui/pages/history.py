"""History and undo: browse past operations and restore files safely."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

from ezsort import engine
from ezsort.gui.pages import Page
from ezsort.gui.theme import short_path
from ezsort.gui.widgets import Card, ToolTip, clear_tree, set_tree_columns

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp


class HistoryPage(Page):
    def __init__(self, app: "EzSortApp", parent):
        super().__init__(
            app, parent,
            "History & Undo",
            "Every sort is recorded here, and every sort can be reversed - "
            "without overwriting anything.",
        )
        self.batches: list[dict] = []
        self._refresh_job: Optional[str] = None
        self._build()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.header.action_button("Refresh", self.refresh)
        self.header.action_button("Undo last sort", self.undo_last,
                                  style="SmallAccent.TButton")

        body = self.body
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        # Toolbar
        toolbar = ttk.Frame(body, style="TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.undo_selected_btn = ttk.Button(
            toolbar, text="Undo selected", style="TButton",
            command=self.undo_selected, state="disabled",
        )
        self.undo_selected_btn.pack(side="left")
        self.delete_btn = ttk.Button(
            toolbar, text="Forget selected", style="Small.TButton",
            command=self.delete_selected, state="disabled",
        )
        self.delete_btn.pack(side="left", padx=(10, 0))
        ttk.Button(
            toolbar, text="Clear all history", style="Danger.TButton",
            command=self.clear_all,
        ).pack(side="right")
        self.count_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=self.count_var, style="Muted.TLabel").pack(
            side="right", padx=(0, 14)
        )

        # Batches
        list_card = Card(body, title="Sort operations")
        list_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        list_card.columnconfigure(0, weight=1)

        list_wrap = ttk.Frame(list_card, style="Surface.TFrame")
        list_wrap.grid(row=1, column=0, sticky="nsew", pady=(4, 4))
        list_wrap.columnconfigure(0, weight=1)
        self.batch_tree = ttk.Treeview(
            list_wrap,
            columns=("ID", "When", "Folder", "Moved", "Failed"),
            show="headings", selectmode="browse", height=6,
        )
        set_tree_columns(self.batch_tree, [
            ("ID", 60, "center"),
            ("When", 150, "w"),
            ("Folder", 280, "w"),
            ("Moved", 70, "e"),
            ("Failed", 70, "e"),
        ])
        bsb = ttk.Scrollbar(list_wrap, orient="vertical",
                            command=self.batch_tree.yview, style="Vertical.TScrollbar")
        self.batch_tree.configure(yscrollcommand=bsb.set)
        self.batch_tree.grid(row=0, column=0, sticky="ew")
        bsb.grid(row=0, column=1, sticky="ns")
        self.batch_tree.bind("<<TreeviewSelect>>", self._on_batch_select)

        # Details
        detail_card = Card(body, title="Files in the selected operation")
        detail_card.grid(row=2, column=0, sticky="nsew")
        detail_card.columnconfigure(0, weight=1)
        detail_card.rowconfigure(1, weight=1)

        detail_wrap = ttk.Frame(detail_card, style="Surface.TFrame")
        detail_wrap.grid(row=1, column=0, sticky="nsew", pady=(4, 4))
        detail_wrap.columnconfigure(0, weight=1)
        detail_wrap.rowconfigure(0, weight=1)
        self.detail_tree = ttk.Treeview(
            detail_wrap,
            columns=("File", "Category", "Original location", "Status"),
            show="headings", selectmode="browse",
        )
        set_tree_columns(self.detail_tree, [
            ("File", 220, "w"),
            ("Category", 130, "w"),
            ("Original location", 320, "w"),
            ("Status", 170, "w"),
        ])
        self.detail_tree.tag_configure("failed", foreground=self.app.palette["danger"])
        dsb = ttk.Scrollbar(detail_wrap, orient="vertical",
                            command=self.detail_tree.yview, style="Vertical.TScrollbar")
        self.detail_tree.configure(yscrollcommand=dsb.set)
        self.detail_tree.grid(row=0, column=0, sticky="nsew")
        dsb.grid(row=0, column=1, sticky="ns")
        self.detail_tree.bind("<<TreeviewSelect>>", self._on_detail_select)

        self.detail_var = tk.StringVar(value="Select an operation to see its files.")
        detail_lbl = ttk.Label(
            detail_card, textvariable=self.detail_var,
            style="SurfaceMuted.TLabel", wraplength=880, justify="left",
        )
        detail_lbl.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ToolTip(detail_lbl, lambda: self.detail_var.get())

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self.batches = engine.load_history()
        clear_tree(self.batch_tree)
        for batch in self.batches:
            when = str(batch.get("timestamp", ""))[:19].replace("T", " ")
            folder = batch.get("folder", "")
            self.batch_tree.insert(
                "", "end",
                values=(
                    batch.get("batch_id", "?"),
                    when,
                    short_path(folder, 42) if folder else "—",
                    batch.get("total_moved", 0),
                    batch.get("total_failed", 0) or "",
                ),
            )
        stats = engine.stats()
        self.count_var.set(
            f"{stats['batches']} operation(s), "
            f"{stats['total_moved']} file(s) organized"
        )
        clear_tree(self.detail_tree)
        self.undo_selected_btn.state(["disabled"])
        self.delete_btn.state(["disabled"])
        self.detail_var.set("Select an operation to see its files.")

    def schedule_refresh(self) -> None:
        """Refresh soon, without blocking the caller (called after sorts)."""
        if self._refresh_job is not None:
            return
        try:
            self._refresh_job = self.app.root.after(300, self._delayed_refresh)
        except Exception:
            self.refresh()

    def _delayed_refresh(self) -> None:
        self._refresh_job = None
        try:
            if self.winfo_exists():
                self.refresh()
        except Exception:
            pass

    def _selected_batch_id(self) -> str | None:
        selection = self.batch_tree.selection()
        if not selection:
            return None
        values = self.batch_tree.item(selection[0], "values")
        return str(values[0]) if values else None

    def _on_batch_select(self, _event=None) -> None:
        batch_id = self._selected_batch_id()
        enabled = batch_id is not None
        self.undo_selected_btn.state(["!disabled"] if enabled else ["disabled"])
        self.delete_btn.state(["!disabled"] if enabled else ["disabled"])
        if batch_id is None:
            return
        batch = engine.load_batch(batch_id)
        clear_tree(self.detail_tree)
        if not batch:
            return
        for op in batch.get("operations", []):
            failed = op.get("status") == "failed"
            status = f"Failed: {op.get('error', '')}" if failed else "Moved"
            self.detail_tree.insert(
                "", "end",
                values=(
                    Path(op.get("source", "")).name,
                    op.get("category", ""),
                    short_path(str(op.get("source", "")), 46),
                    status[:60],
                ),
                tags=("failed",) if failed else (),
            )
        when = str(batch.get("timestamp", ""))[:19].replace("T", " ")
        self.detail_var.set(
            f"Operation {batch.get('batch_id')} at {when} - "
            f"{batch.get('total_moved', 0)} moved"
            + (f", {batch.get('total_failed', 0)} failed"
               if batch.get("total_failed") else "")
            + f"\nFolder: {batch.get('folder', '(not recorded)')}"
        )

    def _on_detail_select(self, _event=None) -> None:
        selection = self.detail_tree.selection()
        if not selection:
            return
        # Show full paths of the selected file operation.
        values = self.detail_tree.item(selection[0], "values")
        batch_id = self._selected_batch_id()
        if not batch_id or len(values) < 3:
            return
        batch = engine.load_batch(batch_id)
        if not batch:
            return
        name = values[0]
        for op in batch.get("operations", []):
            if Path(op.get("source", "")).name == name:
                self.detail_var.set(
                    f"From: {op.get('destination')}\n"
                    f"Back to: {op.get('source')}\n"
                    f"Reason: {op.get('reason', '')}"
                    + (f"\nError: {op.get('error')}" if op.get("error") else "")
                )
                break

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _confirm(self, title: str, message: str) -> bool:
        if not self.app.config.get("confirm_before_move", True):
            return True
        return messagebox.askyesno(title, message, parent=self.app.root)

    def undo_last(self) -> None:
        history = engine.load_history()
        if not history:
            self.app.toast("Nothing to undo yet.", "info")
            return
        if not self._confirm(
            "Undo last sort",
            "Restore the files from the most recent operation to their "
            "original locations?\n\nFiles that already exist at the original "
            "location are never overwritten.",
        ):
            return
        self._run_undo(lambda: engine.undo_last_batch())

    def undo_selected(self) -> None:
        batch_id = self._selected_batch_id()
        if not batch_id:
            self.app.toast("Select an operation first.", "info")
            return
        if not self._confirm(
            f"Undo operation {batch_id}",
            "Restore the files from this operation to their original "
            "locations?",
        ):
            return
        self._run_undo(lambda: engine.undo_specific_batch(batch_id))

    def _run_undo(self, work) -> None:
        def done(result):
            success, message = result
            self.app.log({
                "type": "undone" if success else "failed",
                "message": message,
            })
            self.app.toast(message, "success" if success else "error")
            self.refresh()
            org = self.app.pages.get("organizer")
            if org is not None:
                org.preview = None
            dash = self.app.pages.get("dashboard")
            if dash is not None:
                dash.preview = None

        self.app.start_task("undo", work, on_done=done)

    def delete_selected(self) -> None:
        batch_id = self._selected_batch_id()
        if not batch_id:
            return
        if not messagebox.askyesno(
            "Forget operation",
            f"Remove operation {batch_id} from the history list?\n\n"
            "The files themselves are not touched, but you will no longer "
            "be able to undo it from EzSort.",
            parent=self.app.root,
        ):
            return
        if engine.drop_batch(batch_id):
            self.app.log({"type": "info", "message": f"Forgot operation {batch_id}"})
            self.app.toast(f"Operation {batch_id} removed from history.", "success")
        else:
            self.app.toast("That operation no longer exists.", "error")
        self.refresh()

    def clear_all(self) -> None:
        if not self.batches:
            self.app.toast("History is already empty.", "info")
            return
        if not messagebox.askyesno(
            "Clear history",
            "Delete the entire undo history?\n\nYou will not be able to "
            "undo any previous sort afterwards. Files are not affected.",
            parent=self.app.root,
        ):
            return
        engine.wipe_history()
        self.app.log({"type": "info", "message": "History cleared."})
        self.app.toast("History cleared.", "success")
        self.refresh()

    # ------------------------------------------------------------------

    def on_show(self) -> None:
        self.refresh()

    def apply_theme(self) -> None:
        self.detail_tree.tag_configure("failed", foreground=self.app.palette["danger"])
        super().apply_theme()
