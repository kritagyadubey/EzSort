"""Activity: live progress, per-file results, warnings and errors."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ezsort.activity import clear_activity
from ezsort.gui import theme
from ezsort.gui.components import (
    Card,
    ConfirmDialog,
    SearchBox,
    SegmentedControl,
    ToolTip,
)
from ezsort.gui.pages import Page, sp

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp

KIND_ROLE = {
    "info": "text_secondary",
    "moved": "success",
    "failed": "danger",
    "error": "danger",
    "skipped": "warning",
    "cancelled": "warning",
    "undone": "info",
}


class ActivityPage(Page):
    def __init__(self, app: "EzSortApp", parent):
        super().__init__(
            app, parent,
            "Activity",
            "Live progress and a full account of what EzSort did - "
            "including anything that went wrong.",
        )
        self.counts = {"moved": 0, "failed": 0, "skipped": 0, "error": 0}
        self._entries: list[dict] = []
        self._autoscroll = True
        self._build()
        self._poll_cancel_state()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.header.secondary("Copy log", self.copy_log, style="Ghost.TButton")
        self.header.secondary("Clear log", self.clear_view,
                              style="Ghost.TButton")

        body = self.body
        body.columnconfigure(0, weight=1)
        # Only the event log may flex - the chips keep their natural height.
        body.rowconfigure(0, weight=0)
        body.rowconfigure(1, weight=0)
        body.rowconfigure(2, weight=1)

        top = ttk.Frame(body, style="TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, sp("sm")))
        top.columnconfigure(0, weight=1)

        chips_row = ttk.Frame(top, style="TFrame")
        chips_row.grid(row=0, column=0, sticky="ew")
        self.chip_vars: dict[str, tuple[tk.StringVar, ttk.Label, str]] = {}
        for index, (key, caption, role) in enumerate((
            ("moved", "Moved", "success"),
            ("failed", "Failed", "danger"),
            ("skipped", "Skipped", "warning"),
            ("errors", "Errors", "danger"),
        )):
            chips_row.columnconfigure(index, weight=1, uniform="chip")
            chip = Card(chips_row, padding="sm")
            chip.grid(row=0, column=index, sticky="ew",
                      padx=(0 if index == 0 else sp("sm"), 0))
            var = tk.StringVar(value="0")
            label = ttk.Label(
                chip.body, textvariable=var, style="Stat.TLabel",
                font=theme.font("h2", "bold"),
                foreground=self.app.palette[role],
            )
            label.pack(anchor="w")
            ttk.Label(chip.body, text=caption,
                      style="StatCaption.TLabel").pack(anchor="w")
            self.chip_vars[key] = (var, label, role)

        self.cancel_btn = ttk.Button(
            chips_row, text="Cancel current run", style="Danger.TButton",
            command=self.app.cancel_current,
        )
        self.cancel_btn.grid(row=0, column=4, sticky="e",
                             padx=(sp("sm"), 0))
        self.cancel_btn.state(["disabled"])

        controls = ttk.Frame(top, style="TFrame")
        controls.grid(row=1, column=0, sticky="ew", pady=(sp("sm"), 0))
        controls.columnconfigure(1, weight=1)

        self.filter_var = tk.StringVar(value="all")
        self.filter_control = SegmentedControl(
            controls,
            options=[("all", "All"), ("moved", "Moved"), ("failed", "Failed"),
                     ("skipped", "Skipped"), ("error", "Errors"),
                     ("info", "Info")],
            variable=self.filter_var,
            command=self._rebuild_text,
            bg_style="TFrame",
        )
        self.filter_control.grid(row=0, column=0, sticky="w")

        self.search = SearchBox(
            controls, placeholder="Search the log…", width=24,
            on_change=lambda _t: self._rebuild_text(),
        )
        self.search.grid(row=0, column=1, sticky="e", padx=(sp("sm"), 0))

        # Progress (hidden until a run starts)
        self.progress_frame = ttk.Frame(body, style="TFrame")
        self.progress_frame.grid(row=1, column=0, sticky="ew", pady=(0, sp("sm")))
        self.progress_frame.columnconfigure(0, weight=1)
        self.progress_label_var = tk.StringVar(value="")
        ttk.Label(self.progress_frame, textvariable=self.progress_label_var,
                  style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(
            self.progress_frame, mode="determinate", maximum=100,
        )
        self.progress.grid(row=1, column=0, sticky="ew", pady=(sp("xs"), 0))
        self.progress_frame.grid_remove()

        # Log
        log_card = Card(body, title="Event log")
        log_card.grid(row=2, column=0, sticky="nsew")
        log_card.body.rowconfigure(0, weight=1)
        self.autoscroll_var = tk.BooleanVar(value=True)
        log_card.header.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            log_card.header, text="Auto-scroll", variable=self.autoscroll_var,
            command=lambda: setattr(
                self, "_autoscroll", bool(self.autoscroll_var.get())
            ),
        ).grid(row=0, column=1, sticky="e")
        text_frame = ttk.Frame(log_card.body, style="Surface.TFrame")
        text_frame.grid(row=0, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame, wrap="word", height=14, state="disabled",
            borderwidth=0, highlightthickness=0, padx=sp("sm"),
            pady=sp("sm"), font=theme.font("small", mono=True),
        )
        tsb = ttk.Scrollbar(text_frame, orient="vertical",
                            command=self.text.yview, style="Vertical.TScrollbar")
        self.text.configure(yscrollcommand=tsb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        tsb.grid(row=0, column=1, sticky="ns")
        self.register(self.text, "surface_sunken")
        ToolTip(self.text, "Everything EzSort reports, newest at the bottom.")

        self._configure_tags()

    def _configure_tags(self) -> None:
        palette = self.app.palette
        self.text.configure(
            bg=palette["surface_sunken"], fg=palette["text"],
            insertbackground=palette["text"],
            selectbackground=palette["selection"],
            selectforeground=palette["selection_text"],
        )
        for kind, role in KIND_ROLE.items():
            self.text.tag_configure(kind, foreground=palette[role])
        self.text.tag_configure("time", foreground=palette["text_disabled"])
        self.text.tag_configure("message", foreground=palette["text"])

    # ------------------------------------------------------------------

    def append_entry(self, entry: dict) -> None:
        kind = entry.get("type", "info")
        if kind in self.counts:
            self.counts[kind] += 1
            self._sync_chips()
        self._entries.append(entry)
        if self._matches(entry):
            self._append_line(entry)

    def _matches(self, entry: dict) -> bool:
        kind = str(entry.get("type", "info"))
        selected = self.filter_var.get()
        if selected != "all" and kind != selected:
            return False
        query = self.search.value().lower()
        if query:
            haystack = f"{entry.get('message', '')} {kind}".lower()
            if query not in haystack:
                return False
        return True

    def _sync_chips(self) -> None:
        mapping = {
            "moved": self.counts.get("moved", 0),
            "failed": self.counts.get("failed", 0),
            "skipped": self.counts.get("skipped", 0),
            "errors": self.counts.get("error", 0),
        }
        for key, value in mapping.items():
            self.chip_vars[key][0].set(str(value))

    def _append_line(self, entry: dict) -> None:
        kind = entry.get("type", "info")
        tag = kind if kind in KIND_ROLE else "info"
        self.text.configure(state="normal")
        self.text.insert("end", entry.get("time", ""), ("time",))
        self.text.insert("end", "  ", ())
        self.text.insert("end", entry.get("message", "") + "\n",
                         (tag, "message"))
        if self._autoscroll:
            self.text.see("end")
        self.text.configure(state="disabled")

    def _rebuild_text(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        for entry in self._entries:
            if self._matches(entry):
                self._append_line(entry)

    def render_all(self) -> None:
        self._entries = list(self.app.activity)
        self.counts = {"moved": 0, "failed": 0, "skipped": 0, "error": 0}
        for entry in self._entries:
            kind = entry.get("type", "info")
            if kind in self.counts:
                self.counts[kind] += 1
        self._sync_chips()
        self._rebuild_text()

    def copy_log(self) -> None:
        lines = []
        for entry in self._entries:
            if self._matches(entry):
                lines.append(f"{entry.get('time', '')}  {entry.get('message', '')}")
        if not lines:
            self.app.toast("The log is empty.", "info")
            return
        try:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append("\n".join(lines))
            self.app.toast(f"Copied {len(lines)} log line(s).", "success")
        except Exception as e:  # pragma: no cover
            self.app.toast(f"Could not copy the log: {e}", "error")

    def clear_view(self) -> None:
        if not self._entries:
            self.app.toast("The log is already empty.", "info")
            return
        dialog = ConfirmDialog(
            self.app, "Clear the activity log?",
            "The persisted log is deleted. History and files are not touched.",
            details=f"{len(self._entries)} entry(s) will be removed.",
            confirm_label="Clear log", danger=True,
        )
        if not dialog.show():
            return
        clear_activity()
        self.app.activity.clear()
        self._entries.clear()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.counts = {"moved": 0, "failed": 0, "skipped": 0, "error": 0}
        self._sync_chips()
        self.app.toast("Activity log cleared.", "info")

    # ------------------------------------------------------------------
    # Progress reporting (driven by the organizer page)

    def set_progress(self, done: int, total: int) -> None:
        try:
            self.progress_frame.grid()
            self.progress.configure(maximum=max(1, total), value=done)
            self.progress_label_var.set(
                f"Organizing {done} of {total} file(s)…")
        except Exception:
            pass

    def clear_progress(self) -> None:
        try:
            self.progress_frame.grid_remove()
        except Exception:
            pass

    def _poll_cancel_state(self) -> None:
        """Keep the cancel button honest: enabled only while organizing runs."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        try:
            cancellable = self.app.cancel_token_for("organizing") is not None
            self.cancel_btn.state(["!disabled"] if cancellable else ["disabled"])
        except Exception:
            pass
        try:
            self.after(700, self._poll_cancel_state)
        except Exception:
            pass  # window is going away

    # ------------------------------------------------------------------

    def on_show(self) -> None:
        self.render_all()

    def escape(self) -> None:
        if self.search.value():
            self.search.clear()

    def apply_theme(self) -> None:
        self._configure_tags()
        for key, (_var, label, role) in self.chip_vars.items():
            try:
                label.configure(foreground=self.app.palette[role])
            except Exception:
                pass
        super().apply_theme()
