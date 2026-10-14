"""Activity: live progress, per-file results, warnings and errors."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ezsort.gui.pages import Page
from ezsort.gui.widgets import Card, ToolTip

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp

TAG_COLORS = {
    "info": "#9aa4b2",
    "moved": "#3fb950",
    "failed": "#f85149",
    "error": "#f85149",
    "skipped": "#d29922",
    "undone": "#58a6ff",
}
LIGHT_COLORS = {
    "info": "#5f6b7d",
    "moved": "#1a7f37",
    "failed": "#cf222e",
    "error": "#cf222e",
    "skipped": "#9a6700",
    "undone": "#0969da",
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
        self._autoscroll = True
        self._build()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.header.action_button("Clear view", self.clear_view)

        body = self.body
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        # Chips + controls
        top = ttk.Frame(body, style="TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.chip_vars = {}
        for key, caption, color in (
            ("moved", "Moved", "success"),
            ("failed", "Failed", "danger"),
            ("skipped", "Skipped", "warning"),
            ("errors", "Errors", "danger"),
        ):
            chip = Card(top, title=None)
            chip.pack(side="left", padx=(0, 10))
            var = tk.StringVar(value="0")
            label = ttk.Label(chip, textvariable=var, style="Stat.TLabel",
                              font=("Segoe UI", 15, "bold"), foreground=self.app.palette[color])
            label.pack()
            ttk.Label(chip, text=caption, style="StatCaption.TLabel").pack()
            self.chip_vars[key] = (var, label, color)

        self.cancel_btn = ttk.Button(
            top, text="Cancel current run", style="Danger.TButton",
            command=self.app.cancel_current,
        )
        self.cancel_btn.pack(side="right")

        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top, text="Auto-scroll", variable=self.autoscroll_var,
            command=lambda: setattr(
                self, "_autoscroll", bool(self.autoscroll_var.get())
            ),
        ).pack(side="right", padx=(0, 14))

        # Progress (hidden until a run starts)
        self.progress_frame = ttk.Frame(body, style="TFrame")
        self.progress_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.progress_label_var = tk.StringVar(value="")
        ttk.Label(self.progress_frame, textvariable=self.progress_label_var,
                  style="Muted.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(
            self.progress_frame, mode="determinate", maximum=100, length=260
        )
        self.progress.pack(side="right")
        self.progress_frame.grid_remove()

        # Log
        log_card = Card(body, title="Event log")
        log_card.grid(row=2, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)

        text_frame = ttk.Frame(log_card, style="Surface.TFrame")
        text_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 4))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame, wrap="word", height=16, state="disabled",
            borderwidth=0, highlightthickness=0, padx=10, pady=8,
            font=("Consolas", 10),
        )
        tsb = ttk.Scrollbar(text_frame, orient="vertical",
                            command=self.text.yview, style="Vertical.TScrollbar")
        self.text.configure(yscrollcommand=tsb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        tsb.grid(row=0, column=1, sticky="ns")
        self.register(self.text, "surface")
        ToolTip(self.text, "Everything EzSort reports during this session.")

        self._configure_tags()

    def _configure_tags(self) -> None:
        palette = self.app.palette
        colors = TAG_COLORS if palette["name"] == "dark" else LIGHT_COLORS
        for tag, color in colors.items():
            self.text.tag_configure(tag, foreground=color)
        self.text.tag_configure("time", foreground=palette["muted"])
        self.text.configure(
            bg=palette["surface"], fg=palette["text"],
            insertbackground=palette["text"],
        )

    # ------------------------------------------------------------------

    def append_entry(self, entry: dict) -> None:
        kind = entry.get("type", "info")
        if kind in ("moved", "failed", "skipped", "error"):
            key = kind
            self.counts[key if key in self.counts else "errors"] = (
                self.counts.get(key, 0) + 1
            )
            self._sync_chips()
        self._append_line(entry)

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
        self.text.configure(state="normal")
        self.text.insert("end", entry.get("time", ""), ("time",))
        self.text.insert("end", "  " + entry.get("message", "") + "\n", (kind,))
        if self.autoscroll_var.get():
            self.text.see("end")
        self.text.configure(state="disabled")

    def render_all(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.counts = {"moved": 0, "failed": 0, "skipped": 0, "error": 0}
        for entry in self.app.activity:
            self.append_entry(entry)

    def clear_view(self) -> None:
        self.app.activity.clear()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.counts = {"moved": 0, "failed": 0, "skipped": 0, "error": 0}
        self._sync_chips()
        self.app.toast("Activity view cleared.", "info")

    # ------------------------------------------------------------------
    # Progress reporting (driven by the organizer page)

    def set_progress(self, done: int, total: int) -> None:
        try:
            self.progress_frame.grid()
            self.progress.configure(maximum=max(1, total), value=done)
            self.progress_label_var.set(f"Organizing {done} / {total} files…")
        except Exception:
            pass

    def clear_progress(self) -> None:
        try:
            self.progress_frame.grid_remove()
        except Exception:
            pass

    # ------------------------------------------------------------------

    def on_show(self) -> None:
        self.render_all()

    def apply_theme(self) -> None:
        self._configure_tags()
        for key, (var, label, color) in self.chip_vars.items():
            try:
                label.configure(fg=self.app.palette[color])
            except Exception:
                pass
        super().apply_theme()
