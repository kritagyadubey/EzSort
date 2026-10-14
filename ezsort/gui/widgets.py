"""Reusable visual building blocks for the EzSort interface."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class Card(ttk.Frame):
    """A raised surface panel used to group related controls."""

    def __init__(self, parent, title: str | None = None, **kwargs):
        super().__init__(parent, style="Surface.TFrame", padding=16, **kwargs)
        self.columnconfigure(0, weight=1)
        if title:
            ttk.Label(self, text=title, style="CardTitle.TLabel").grid(
                row=0, column=0, sticky="w", pady=(0, 10)
            )
            self._next_row = 1
        else:
            self._next_row = 0

    def add(self, widget, sticky="ew", pady=(0, 0), padx=0) -> None:
        """Place a widget in the next row of the card."""
        widget.grid(row=self._next_row, column=0, sticky=sticky, pady=pady, padx=padx)
        self._next_row += 1

    @property
    def next_row(self) -> int:
        return self._next_row

    def bump(self, rows: int = 1) -> None:
        self._next_row += rows


class PageHeader(ttk.Frame):
    """Page title + optional subtitle + trailing action buttons."""

    def __init__(self, parent, title: str, subtitle: str = ""):
        super().__init__(parent, style="TFrame")
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text=title, style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        if subtitle:
            ttk.Label(self, text=subtitle, style="Subtitle.TLabel").grid(
                row=1, column=0, sticky="w", pady=(4, 0)
            )
        self._actions = ttk.Frame(self, style="TFrame")
        self._actions.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(12, 0))

    def action_button(self, text, command, style: str = "Small.TButton"):
        """Create and place a header action button (correct parent)."""
        button = ttk.Button(self._actions, text=text, command=command, style=style)
        button.pack(side="left", padx=(6, 0))
        return button

    def add_action(self, widget) -> None:
        """Place a widget that was built inside the action slot."""
        widget.pack(side="left", padx=(6, 0))


class ScrollableFrame(ttk.Frame):
    """A canvas with a vertical scrollbar that hosts a scrollable column frame."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self, highlightthickness=0, borderwidth=0, takefocus=0
        )
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview,
            style="Vertical.TScrollbar"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.body = ttk.Frame(self.canvas, style="TFrame")
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._window, width=e.width),
        )
        # Mouse-wheel: bind on the toplevel (part of every widget's
        # bindtags), then ignore events that arrive from other widgets.
        top = self.winfo_toplevel()
        top.bind("<MouseWheel>", self._on_wheel, add="+")
        top.bind("<Button-4>", self._on_wheel, add="+")
        top.bind("<Button-5>", self._on_wheel, add="+")

    def _on_wheel(self, event) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        widget = event.widget
        while widget is not None:
            if widget is self.canvas:
                break
            widget = getattr(widget, "master", None)
        else:
            return  # event came from somewhere else on the page
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-2, "units")
        else:
            self.canvas.yview_scroll(2, "units")


class ToolTip:
    """Simple hover tooltip for widgets with truncated text."""

    def __init__(self, widget, text: Callable[[], str] | str, delay: int = 350):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id: Optional[str] = None
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None) -> None:
        self._cancel()
        try:
            self._after_id = self.widget.after(self.delay, self._show)
        except Exception:
            pass

    def _cancel(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        content = self.text() if callable(self.text) else self.text
        if not content:
            return
        self._hide()
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        label = tk.Label(
            tip,
            text=content,
            justify="left",
            background="#1c2230",
            foreground="#e6edf3",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
            font=("Segoe UI", 9),
            wraplength=460,
        )
        label.pack()
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        tip.wm_geometry(f"+{x}+{y}")
        self._tip = tip

    def _hide(self, event=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def make_tooltip(widget, text: Callable[[], str] | str) -> ToolTip:
    return ToolTip(widget, text)


def bind_treeview_shortcuts(tree: ttk.Treeview, on_activate: Callable[[], None]) -> None:
    """Double-click / Enter activation for tables."""
    tree.bind("<Double-1>", lambda e: on_activate(), add="+")
    tree.bind("<Return>", lambda e: on_activate(), add="+")


def clear_tree(tree: ttk.Treeview) -> None:
    for item in tree.get_children():
        tree.delete(item)


def set_tree_columns(tree: ttk.Treeview, columns: list[tuple[str, int, str]]) -> None:
    """Configure columns as ``(id, width, anchor)`` tuples."""
    tree.configure(columns=[c[0] for c in columns])
    tree.heading("#0", text="")
    tree.column("#0", width=0, stretch=False)
    for col_id, width, anchor in columns:
        tree.heading(col_id, text=col_id)
        tree.column(col_id, width=width, anchor=anchor, stretch=(anchor == "w"))
