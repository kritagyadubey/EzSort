"""History and undo: browse past operations and restore files safely."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from ezsort import engine
from ezsort.gui.components import (
    Badge,
    Card,
    ConfirmDialog,
    SearchBox,
    Table,
    ToolTip,
)
from ezsort.gui.pages import Page, sp
from ezsort.gui.theme import middle_ellipsis, short_path
from ezsort.utils import path_exists

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
        #: Operations of the batch currently shown in the detail table,
        #: indexed by the tree row ids ("0", "1", ...).
        self._detail_ops: list[dict] = []
        self._refresh_job: Optional[str] = None
        self._row_order: list[str] = []
        self._row_meta: dict[str, tuple[str, str]] = {}
        self._build()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.header.secondary("Refresh", self.refresh, style="Ghost.TButton")
        self.header.primary("Undo last sort", self.undo_last)

        body = self.body
        body.columnconfigure(0, weight=1)
        # The toolbar and the operation list keep their natural height; the
        # detail card takes the rest so its table and summary always fit.
        body.rowconfigure(0, weight=0)
        body.rowconfigure(1, weight=0)
        body.rowconfigure(2, weight=1)

        # Toolbar
        toolbar = ttk.Frame(body, style="TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, sp("sm")))
        toolbar.columnconfigure(3, weight=1)
        self.undo_selected_btn = ttk.Button(
            toolbar, text="Undo selected", style="Secondary.TButton",
            command=self.undo_selected, state="disabled",
        )
        self.undo_selected_btn.grid(row=0, column=0, sticky="w")
        self.delete_btn = ttk.Button(
            toolbar, text="Forget selected", style="Ghost.TButton",
            command=self.delete_selected, state="disabled",
        )
        self.delete_btn.grid(row=0, column=1, padx=(sp("sm"), 0), sticky="w")
        ttk.Button(
            toolbar, text="Clear all history", style="Danger.TButton",
            command=self.clear_all,
        ).grid(row=0, column=2, sticky="w", padx=(sp("sm"), 0))

        self.search = SearchBox(
            toolbar, placeholder="Search history…", width=26,
            on_change=lambda _t: self._apply_filter(),
        )
        self.search.grid(row=0, column=3, sticky="e", padx=(sp("sm"), 0))
        self.count_var = tk.StringVar(value="")

        # Batches
        list_card = Card(body, title="Sort operations")
        list_card.grid(row=1, column=0, sticky="ew", pady=(0, sp("md")))
        self.batch_badge = Badge(list_card.header, "0", "muted")
        self.batch_badge.grid(row=0, column=1, sticky="e")
        self.batch_table = Table(
            list_card.body,
            columns=[
                ("ID", "Batch", 64, "center"),
                ("When", "When", 160, "w"),
                ("Folder", "Folder", 280, "w"),
                ("Moved", "Moved", 70, "e"),
                ("Failed", "Failed", 70, "e"),
                ("Status", "Status", 170, "w"),
            ],
            height=4,
            on_select=self._on_batch_select,
            empty_text="No sorts recorded yet - organize a folder first.",
        )
        self.batch_table.grid(row=0, column=0, sticky="ew")
        self.batch_tree = self.batch_table.tree

        # Details
        detail_card = Card(body, title="Files in the selected operation")
        detail_card.grid(row=2, column=0, sticky="nsew")
        detail_card.body.rowconfigure(0, weight=1)
        self.detail_badge = Badge(detail_card.header, "No selection", "muted")
        self.detail_badge.grid(row=0, column=1, sticky="e")

        self.detail_table = Table(
            detail_card.body,
            columns=[
                ("File", "File", 220, "w"),
                ("Category", "Category", 130, "w"),
                ("Original location", "Original location", 320, "w"),
                ("Status", "Status", 170, "w"),
            ],
            height=7,
            on_select=self._on_detail_select,
            empty_text="Select an operation above to see its files.",
        )
        self.detail_table.grid(row=0, column=0, sticky="nsew")
        self.detail_tree = self.detail_table.tree

        self.detail_var = tk.StringVar(value="Select an operation to see its files.")
        detail_lbl = ttk.Label(
            detail_card.body, textvariable=self.detail_var,
            style="SurfaceMuted.TLabel", justify="left", anchor="w",
        )
        detail_lbl.grid(row=1, column=0, sticky="ew", pady=(sp("sm"), 0))
        detail_card.body.bind(
            "<Configure>",
            lambda e: detail_lbl.configure(wraplength=max(sp("lg") * 8,
                                                         e.width - sp("sm"))),
        )
        ToolTip(detail_lbl, lambda: self.detail_var.get())

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self.batches = engine.load_history()
        self.batch_table.clear()
        self._row_order.clear()
        self._row_meta.clear()
        for index, batch in enumerate(self.batches):
            when = str(batch.get("timestamp", ""))[:19].replace("T", " ")
            folder = batch.get("folder", "")
            failed = int(batch.get("total_failed", 0) or 0)
            status = self._batch_status(batch)
            tags = list(("odd",) if index % 2 else ())
            if failed:
                tags.append("failed")
            if batch.get("undone"):
                tags.append("undone")
            elif status == "Cancelled":
                tags.append("cancelled")
            item = self.batch_table.insert_row(
                (
                    batch.get("batch_id", "?"),
                    when,
                    short_path(folder, 42) if folder else "—",
                    batch.get("total_moved", 0),
                    failed or "",
                    status,
                ),
                tags=tags,
                iid=str(index),
                cell_text={"Folder": folder or ""},
            )
            self._row_order.append(item)
            self._row_meta[item] = (
                f"{batch.get('batch_id', '')} {when} {folder} {status}".lower(),
                "undone" if batch.get("undone") else (
                    "cancelled" if status == "Cancelled" else "active"),
            )

        stats = engine.stats()
        self.count_var.set(
            f"{stats['batches']} operation(s), "
            f"{stats['total_moved']} file(s) organized"
            + (f", {stats['undone_batches']} undone"
               if stats.get("undone_batches") else "")
        )
        self.batch_badge.set(f"{len(self.batches)} record(s)", "neutral")
        self.detail_table.clear()
        self._detail_ops = []
        self.undo_selected_btn.state(["disabled"])
        self.delete_btn.state(["disabled"])
        self.detail_var.set("Select an operation to see its files.")
        self.detail_badge.set("No selection", "muted")
        self._apply_filter()

    @staticmethod
    def _batch_status(batch: dict) -> str:
        if batch.get("undone"):
            return "Undone"
        status = str(batch.get("status", "completed"))
        if status == "cancelled":
            return "Cancelled"
        if status == "partial":
            return "Partly undone"
        if int(batch.get("total_failed", 0) or 0):
            return "Completed with errors"
        return "Completed"

    def _apply_filter(self) -> None:
        query = self.search.value().lower()
        visible = 0
        for item in self._row_order:
            text, _kind = self._row_meta.get(item, ("", "active"))
            match = not query or query in text
            try:
                if match:
                    self.batch_tree.reattach(item, "", "end")
                    visible += 1
                else:
                    self.batch_tree.detach(item)
            except tk.TclError:
                pass
        if query:
            self.batch_badge.set(f"{visible} of {len(self._row_order)} record(s)",
                                 "accent" if visible else "muted")
        else:
            self.batch_badge.set(f"{len(self._row_order)} record(s)", "neutral")

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
        self.delete_btn.state(["!disabled"] if enabled else ["disabled"])
        if batch_id is None:
            self.undo_selected_btn.state(["disabled"])
            return
        batch = engine.load_batch(batch_id)
        self.detail_table.clear()
        if not batch:
            self.undo_selected_btn.state(["disabled"])
            return
        can_undo = bool(batch.get("operations")) and not batch.get("undone")
        self.undo_selected_btn.state(["!disabled"] if can_undo else ["disabled"])

        for index, op in enumerate(batch.get("operations", [])):
            failed = op.get("status") == "failed"
            if failed:
                status = f"Failed: {op.get('error', '')}"
            elif op.get("status") == "undone":
                status = "Undone"
            else:
                status = "Moved"
            self.detail_table.insert_row(
                (
                    middle_ellipsis(Path(op.get("source", "")).name, 40),
                    middle_ellipsis(op.get("category", ""), 26),
                    short_path(str(op.get("source", "")), 52),
                    middle_ellipsis(status, 34),
                ),
                tags=(*self._row_tag(index), "failed") if failed else self._row_tag(index),
                iid=str(index),
                cell_text={"Original location": str(op.get("source", "")),
                           "Status": status},
            )
        self._detail_ops = batch.get("operations", [])
        when = str(batch.get("timestamp", ""))[:19].replace("T", " ")
        status = self._batch_status(batch)
        ready, blocked, missing, failed = self._undo_preview(batch)
        summary = (
            f"Operation {batch.get('batch_id')} at {when} - {status}\n"
            f"{batch.get('total_moved', 0)} moved"
            + (f", {batch.get('total_failed', 0)} failed"
               if batch.get("total_failed") else "")
            + (f", {batch.get('total_planned')} planned"
               if batch.get("total_planned") else "")
            + f"\nFolder: {batch.get('folder', '(not recorded)')}"
        )
        if can_undo:
            summary += (
                f"\nUndo preview: {ready} ready"
                + (f", {blocked} blocked by an existing file" if blocked else "")
                + (f", {missing} already gone" if missing else "")
                + (f", {failed} failed (not undoable)" if failed else "")
            )
        elif batch.get("undone"):
            summary += "\nThis operation has already been undone."
        self.detail_var.set(summary)
        self.detail_badge.set(status, self._status_kind(batch))

    @staticmethod
    def _status_kind(batch: dict) -> str:
        if batch.get("undone"):
            return "muted"
        status = str(batch.get("status", "completed"))
        if status == "cancelled":
            return "warning"
        if status == "partial":
            return "warning"
        if int(batch.get("total_failed", 0) or 0):
            return "danger"
        return "success"

    @staticmethod
    def _undo_preview(batch: dict) -> tuple[int, int, int, int]:
        """Count files that can be restored right now (honest preview)."""
        ready = blocked = missing = failed = 0
        for op in batch.get("operations", []):
            if op.get("status") == "failed":
                failed += 1
                continue
            if op.get("status") == "undone":
                continue
            source = Path(op.get("source", ""))
            dest = Path(op.get("destination", ""))
            if not path_exists(dest):
                missing += 1
            elif path_exists(source):
                blocked += 1
            else:
                ready += 1
        return ready, blocked, missing, failed

    @staticmethod
    def _row_tag(index: int) -> tuple[str, ...]:
        return ("odd",) if index % 2 else ()

    def _on_detail_select(self, _event=None) -> None:
        selection = self.detail_tree.selection()
        if not selection:
            return
        # Map the selected row straight to its operation. Row ids are the
        # operation indices, so duplicate filenames resolve correctly.
        try:
            op = self._detail_ops[int(selection[0])]
        except (ValueError, IndexError):
            return
        self.detail_var.set(
            f"From: {op.get('destination')}\n"
            f"Back to: {op.get('source')}\n"
            f"Reason: {op.get('reason', '')}"
            + (f"\nError: {op.get('error')}" if op.get("error") else "")
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def undo_last(self) -> None:
        history = engine.load_history()
        usable = [b for b in history
                  if b.get("operations") and not b.get("undone")]
        if not usable:
            self.app.toast("Nothing to undo yet.", "info")
            return
        batch = usable[-1]
        if self.app.config.get("confirm_before_move", True):
            ready, blocked, missing, _failed = self._undo_preview(batch)
            dialog = ConfirmDialog(
                self.app, "Undo the last sort?",
                "Files from this sort will move back to where they came from.",
                details=(
                    f"Batch {batch.get('batch_id')} - "
                    f"{batch.get('total_moved', 0)} file(s)\n"
                    f"Folder: {batch.get('folder', '(not recorded)')}\n\n"
                    f"{ready} ready to restore"
                    + (f", {blocked} blocked" if blocked else "")
                    + (f", {missing} already gone" if missing else "")
                    + "\n\nNothing at the original location is ever overwritten."
                ),
                confirm_label="Undo this sort",
            )
            if not dialog.show():
                return
        self._run_undo(engine.undo_last_report)

    def undo_selected(self) -> None:
        batch_id = self._selected_batch_id()
        if not batch_id:
            self.app.toast("Select an operation first.", "info")
            return
        batch = engine.load_batch(batch_id) or {}
        if batch.get("undone") or not batch.get("operations"):
            self.app.toast("That operation has nothing left to undo.", "info")
            return
        if self.app.config.get("confirm_before_move", True):
            ready, blocked, missing, _failed = self._undo_preview(batch)
            dialog = ConfirmDialog(
                self.app, f"Undo operation {batch_id}?",
                "Files from this operation will move back to their original "
                "locations.",
                details=(f"{ready} ready to restore"
                         + (f", {blocked} blocked" if blocked else "")
                         + (f", {missing} already gone" if missing else "")),
                confirm_label="Undo this operation",
            )
            if not dialog.show():
                return
        self._run_undo(lambda: engine.undo_specific_report(batch_id))

    def _run_undo(self, work) -> None:
        def done(report):
            self.app.log({
                "type": "undone" if report.success else "failed",
                "message": report.message,
            })
            self.app.toast(report.message, "success" if report.success else "error")
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
        dialog = ConfirmDialog(
            self.app, "Forget this operation?",
            "The record is removed from the history list. Files are not touched.",
            details=(f"Batch {batch_id} will no longer be undoable from EzSort."),
            confirm_label="Forget operation", danger=True,
        )
        if not dialog.show():
            return
        if engine.drop_batch(batch_id):
            self.app.log({"type": "info",
                          "message": f"Forgot operation {batch_id}"})
            self.app.toast(f"Operation {batch_id} removed from history.",
                           "success")
        else:
            self.app.toast("That operation no longer exists.", "error")
        self.refresh()

    def clear_all(self) -> None:
        if not self.batches:
            self.app.toast("History is already empty.", "info")
            return
        dialog = ConfirmDialog(
            self.app, "Clear all history?",
            "Every undo record is deleted. Files are not touched, but no "
            "previous sort can be undone afterwards.",
            details=f"{len(self.batches)} record(s) will be removed.",
            confirm_label="Clear history", danger=True,
        )
        if not dialog.show():
            return
        engine.wipe_history()
        self.app.log({"type": "info", "message": "History cleared."})
        self.app.toast("History cleared.", "success")
        self.refresh()

    # ------------------------------------------------------------------

    def on_show(self) -> None:
        self.refresh()

    def escape(self) -> None:
        if self.search.value():
            self.search.clear()

    def apply_theme(self) -> None:
        self.batch_table.apply_theme(self.app.palette)
        self.detail_table.apply_theme(self.app.palette)
        super().apply_theme()
