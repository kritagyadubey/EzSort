"""Shared UI components for the EzSort desktop app.

Every component is themed exclusively through ttk styles or through the
``apply_theme`` protocol, so switching themes updates open widgets and
dialogs without a restart. Components that draw on a raw Tk canvas expose
``apply_theme`` and are re-skinned by their owning page or by the app's
theme walk.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Optional, Sequence

from ezsort.gui import icons, theme, tokens
from ezsort.gui.tokens import SPACE


def sp(key: str) -> int:
    """Scaled spacing token."""
    return tokens.sc(SPACE[key])


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------

class IconCanvas(tk.Canvas):
    """A themed vector icon."""

    THEME_AWARE = True

    def __init__(self, parent, name: str, role: str = "text_secondary",
                 size: Optional[int] = None, bg_role: str = "bg"):
        self._size = size or tokens.sc(icons.SIZE)
        self._role = role
        self._bg_role = bg_role
        palette = theme.active_palette()
        super().__init__(parent, width=self._size, height=self._size,
                         bg=palette[bg_role], highlightthickness=0,
                         borderwidth=0, takefocus=0)
        self._name = name
        self.apply_theme(palette)

    def configure_icon(self, name: str, role: Optional[str] = None) -> None:
        self._name = name
        if role:
            self._role = role
        self.apply_theme(theme.active_palette())

    def set_roles(self, bg_role: str, role: str) -> None:
        """Recolour the icon for a new surface/foreground role."""
        self._bg_role = bg_role
        self._role = role
        self.apply_theme(theme.active_palette())

    def apply_theme(self, palette: dict) -> None:
        try:
            self.configure(bg=palette[self._bg_role])
            icons.draw_icon(self, self._name, palette[self._role], self._size)
        except tk.TclError:  # pragma: no cover - widget destroyed
            pass


class Card(ttk.Frame):
    """A bordered surface panel with consistent interior padding."""

    def __init__(self, parent, title: str | None = None,
                 subtitle: str | None = None, padding: str = "lg",
                 **kwargs):
        super().__init__(parent, style="Card.TFrame", **kwargs)
        pad = sp(padding)
        self.inner = ttk.Frame(self, style="Surface.TFrame",
                               padding=(pad, pad, pad, pad))
        self.inner.pack(fill="both", expand=True)
        self.inner.columnconfigure(0, weight=1)
        self._next_row = 0
        if title:
            header = ttk.Frame(self.inner, style="Surface.TFrame")
            header.grid(row=0, column=0, sticky="ew", pady=(0, sp("md")))
            header.columnconfigure(0, weight=1)
            ttk.Label(header, text=title, style="CardTitle.TLabel").grid(
                row=0, column=0, sticky="w")
            self.header = header
            self._next_row = 1
            if subtitle:
                ttk.Label(header, text=subtitle, style="SurfaceMuted.TLabel",
                          wraplength=tokens.sc(520), justify="left").grid(
                    row=1, column=0, sticky="w", pady=(sp("xs"), 0))
        else:
            self.header = None
        self.body = ttk.Frame(self.inner, style="Surface.TFrame")
        self.body.grid(row=self._next_row, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.inner.rowconfigure(self._next_row, weight=1)
        self._next_row += 1

    def add(self, widget, sticky: str = "ew", pady=(0, 0), padx=0,
            row: Optional[int] = None, column: int = 0) -> None:
        """Place a widget in the next row of the card body."""
        index = self._next_row if row is None else row
        if row is None:
            self._next_row += 1
        widget.grid(row=index, column=column, sticky=sticky, pady=pady,
                    padx=padx)

    @property
    def next_row(self) -> int:
        return self._next_row

    def bump(self, rows: int = 1) -> None:
        self._next_row += rows


class PageHeader(ttk.Frame):
    """Page title, one-line purpose, and a right-aligned action area."""

    def __init__(self, parent, title: str, purpose: str = ""):
        super().__init__(parent, style="TFrame")
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text=title, style="Title.TLabel").grid(
            row=0, column=0, sticky="w")
        self._purpose: Optional[ttk.Label] = None
        if purpose:
            self._purpose = ttk.Label(
                self, text=purpose, style="Subtitle.TLabel", justify="left",
                wraplength=tokens.sc(620),
            )
            self._purpose.grid(row=1, column=0, sticky="w", pady=(sp("xs"), 0))
        self._actions = ttk.Frame(self, style="TFrame")
        self._actions.grid(row=0, column=1, rowspan=2, sticky="ne")
        self.primary_button: Optional[ttk.Button] = None
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event) -> None:
        """Wrap the purpose line instead of letting actions clip it."""
        if self._purpose is None:
            return
        actions = self._actions.winfo_reqwidth()
        available = max(sp("lg") * 6, int(event.width) - actions - sp("md"))
        available = min(available, tokens.sc(620))
        try:
            self._purpose.configure(wraplength=available)
        except tk.TclError:  # pragma: no cover - widget destroyed
            pass

    def primary(self, text: str, command: Callable[[], None],
                style: str = "Primary.TButton") -> ttk.Button:
        button = ttk.Button(self._actions, text=text, command=command,
                            style=style)
        button.pack(side="right", padx=(sp("sm"), 0))
        self.primary_button = button
        return button

    def secondary(self, text: str, command: Callable[[], None],
                  style: str = "Secondary.TButton") -> ttk.Button:
        button = ttk.Button(self._actions, text=text, command=command,
                            style=style)
        button.pack(side="right", padx=(sp("sm"), 0))
        return button

    def action_button(self, text, command, style: str = "Small.TButton"):
        """Backward-compatible alias used by older call sites."""
        button = ttk.Button(self._actions, text=text, command=command,
                            style=style)
        button.pack(side="left", padx=(sp("sm"), 0))
        return button

    def add_action(self, widget) -> None:
        widget.pack(side="right", padx=(sp("sm"), 0))


class Badge(ttk.Label):
    """A compact semantic status chip."""

    KINDS = {
        "neutral": "BadgeNeutral.TLabel",
        "accent": "BadgeAccent.TLabel",
        "success": "BadgeSuccess.TLabel",
        "warning": "BadgeWarning.TLabel",
        "danger": "BadgeDanger.TLabel",
        "info": "BadgeInfo.TLabel",
        "muted": "BadgeMuted.TLabel",
    }

    def __init__(self, parent, text: str, kind: str = "neutral", **kwargs):
        super().__init__(parent, text=text, style=self.KINDS.get(kind, "BadgeNeutral.TLabel"),
                         **kwargs)

    def set(self, text: str, kind: str = "neutral") -> None:
        self.configure(text=text, style=self.KINDS.get(kind, "BadgeNeutral.TLabel"))


class Divider(ttk.Frame):
    def __init__(self, parent, pady: int = 0):
        super().__init__(parent, style="Divider.TFrame", height=tokens.sc(1))
        self.pack_propagate(False)


class InlineBanner(ttk.Frame):
    """A persistent, themed inline message (not a modal dialog)."""

    THEME_AWARE = True

    KIND_STYLES = {
        "info": ("BannerInfo", "info", "info", "info_bg"),
        "success": ("BannerSuccess", "success", "success", "success_bg"),
        "warning": ("BannerWarning", "warning", "warning", "warning_bg"),
        "danger": ("BannerDanger", "danger", "danger", "danger_bg"),
        "neutral": ("BannerNeutral", "text_secondary", "info", "surface_alt"),
    }

    def __init__(self, parent, message: str = "", kind: str = "info",
                 title: str = "", show_icon: bool = True):
        self._kind = kind if kind in self.KIND_STYLES else "info"
        prefix, role, icon, bg_role = self.KIND_STYLES[self._kind]
        self._bg_role = bg_role
        super().__init__(parent, style=f"{prefix}.TFrame", padding=(sp("md"), sp("sm")))
        self.columnconfigure(1, weight=1)
        self._icon: Optional[IconCanvas] = None
        if show_icon:
            self._icon = IconCanvas(self, icon, role=role,
                                    bg_role=bg_role, size=tokens.sc(16))
            self._icon.grid(row=0, column=0, rowspan=2, sticky="n",
                            padx=(0, sp("sm")), pady=(sp("xs"), 0))
        self.title_var = tk.StringVar(value=title)
        self.message_var = tk.StringVar(value=message)
        self._title = ttk.Label(self, textvariable=self.title_var,
                                style=f"{prefix}Strong.TLabel")
        self._title.grid(row=0, column=1, sticky="w")
        if not title:
            self._title.grid_remove()
        self._message = ttk.Label(self, textvariable=self.message_var,
                                  style=f"{prefix}Body.TLabel",
                                  wraplength=tokens.sc(760), justify="left")
        self._message.grid(row=1 if title else 0, column=1, sticky="w",
                           pady=(sp("xs"), 0) if title else (0, 0))
        self._action: Optional[ttk.Button] = None
        self._action_col = 2
        self.bind("<Configure>", self._rewrap)

    def _rewrap(self, event) -> None:
        width = max(240, event.width - tokens.sc(80))
        try:
            self._message.configure(wraplength=width)
        except tk.TclError:
            pass

    def set(self, message: str, kind: Optional[str] = None,
            title: Optional[str] = None) -> None:
        if kind and kind != self._kind:
            # Rebuild styles without recreating the widget tree.
            self._kind = kind if kind in self.KIND_STYLES else "info"
            prefix = self.KIND_STYLES[self._kind][0]
            self.configure(style=f"{prefix}.TFrame")
            self._title.configure(style=f"{prefix}Strong.TLabel")
            self._message.configure(style=f"{prefix}Body.TLabel")
        self.message_var.set(message)
        if title is not None:
            self.title_var.set(title)
            if title:
                self._title.grid()
            else:
                self._title.grid_remove()
        self.grid()

    def set_action(self, text: str, command: Callable[[], None]) -> ttk.Button:
        if self._action is not None:
            self._action.destroy()
        self._action = ttk.Button(self, text=text, command=command,
                                  style="Small.TButton")
        self._action.grid(row=0, column=self._action_col, rowspan=2,
                          sticky="e", padx=(sp("sm"), 0))
        return self._action

    def apply_theme(self, palette: dict) -> None:
        if self._icon is not None:
            _prefix, role, icon, bg_role = self.KIND_STYLES[self._kind]
            self._icon.set_roles(bg_role, role)
            self._icon.configure_icon(icon, role)


class EmptyState(ttk.Frame):
    """A deliberate empty state: icon, explanation and next step."""

    def __init__(self, parent, title: str, body: str = "", icon: str = "folder",
                 action: Optional[tuple[str, Callable[[], None]]] = None,
                 bg_role: str = "surface"):
        super().__init__(parent, style="Surface.TFrame" if bg_role == "surface" else "TFrame")
        self._bg_role = bg_role
        self.columnconfigure(0, weight=1)
        self._icon = IconCanvas(self, icon, role="text_disabled",
                                size=tokens.sc(30), bg_role=bg_role)
        self._icon.grid(row=0, column=0, pady=(sp("md"), sp("sm")))
        self._title = ttk.Label(
            self, text=title,
            style="Surface.TLabel" if bg_role == "surface" else "TLabel",
            font=theme.font("h2", "bold"))
        self._title.grid(row=1, column=0)
        self._body = ttk.Label(
            self, text=body, justify="center", wraplength=tokens.sc(420),
            style="SurfaceMuted.TLabel" if bg_role == "surface" else "Muted.TLabel")
        self._body.grid(row=2, column=0, pady=(sp("xs"), sp("md")))
        if action:
            label, command = action
            self._action = ttk.Button(self, text=label, command=command,
                                      style="Primary.TButton")
            self._action.grid(row=3, column=0, pady=(0, sp("md")))

    def set(self, title: str, body: str = "") -> None:
        self._title.configure(text=title)
        self._body.configure(text=body)


class SegmentedControl(ttk.Frame):
    """A keyboard-accessible segmented choice (radio semantics)."""

    def __init__(self, parent, options: Sequence[tuple[str, str]],
                 variable: tk.StringVar, command: Optional[Callable[[], None]] = None,
                 bg_style: str = "Surface.TFrame"):
        super().__init__(parent, style=bg_style)
        self.variable = variable
        self._buttons: list[ttk.Radiobutton] = []
        for index, (value, label) in enumerate(options):
            button = ttk.Radiobutton(
                self, text=label, value=value, variable=variable,
                style="Segment.Toolbutton", command=command,
                takefocus=True,
            )
            button.pack(side="left", padx=(0 if index == 0 else sp("xs"), 0))
            self._buttons.append(button)

    def set(self, value: str) -> None:
        self.variable.set(value)


class Field(ttk.Frame):
    """Label + entry + hint/error, with real validation styling."""

    def __init__(self, parent, label: str, hint: str = "",
                 bg_role: str = "surface", show_label: bool = True):
        style = "Surface.TFrame" if bg_role == "surface" else "TFrame"
        super().__init__(parent, style=style)
        self.columnconfigure(0, weight=1)
        self._label_style = ("Surface.TLabel" if bg_role == "surface" else "TLabel")
        self._hint_style = ("SurfaceMuted.TLabel" if bg_role == "surface"
                            else "Muted.TLabel")
        self._row = 0
        if show_label:
            ttk.Label(self, text=label, style=self._label_style).grid(
                row=0, column=0, sticky="w", pady=(0, sp("xs")))
            self._row = 1
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, style="TEntry")
        self.entry.grid(row=self._row, column=0, sticky="ew")
        self._hint = ttk.Label(self, text=hint, style=self._hint_style,
                               wraplength=tokens.sc(420), justify="left")
        self._hint.grid(row=self._row + 1, column=0, sticky="w",
                        pady=(sp("xs"), 0))
        self._hint_visible = bool(hint)
        if not hint:
            self._hint.grid_remove()

    def set_error(self, message: str) -> None:
        self.entry.configure(style="Error.TEntry")
        self._hint.configure(text=message, style="SurfaceDanger.TLabel")
        self._hint.grid()

    def set_ok(self, message: str = "") -> None:
        self.entry.configure(style="Success.TEntry")
        if message:
            self._hint.configure(text=message, style="SurfaceSuccess.TLabel")
            self._hint.grid()
        elif not self._hint_visible:
            self._hint.grid_remove()

    def clear_state(self, hint: str = "") -> None:
        self.entry.configure(style="TEntry")
        if hint:
            self._hint.configure(text=hint, style=self._hint_style)
            self._hint.grid()
        elif not self._hint_visible:
            self._hint.grid_remove()

    def focus_entry(self) -> None:
        self.entry.focus_set()


class SearchBox(ttk.Frame):
    """Search entry with placeholder text and a clear button."""

    def __init__(self, parent, placeholder: str = "Search",
                 variable: Optional[tk.StringVar] = None,
                 width: int = 32, on_change: Optional[Callable[[str], None]] = None):
        super().__init__(parent, style="Surface.TFrame")
        self.columnconfigure(0, weight=1)
        self.var = variable or tk.StringVar()
        self._placeholder = placeholder
        self._showing_placeholder = False
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.grid(row=0, column=0, sticky="ew")
        self._clear = ttk.Button(self, text="x", style="SurfaceGhost.TButton",
                                 command=self.clear, takefocus=False)
        self._clear.grid(row=0, column=1, padx=(sp("xs"), 0))
        self._clear.grid_remove()
        self.var.trace_add("write", self._on_write)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Escape>", lambda e: self.clear())
        self._on_change = on_change
        self._apply_placeholder()

    def _apply_placeholder(self) -> None:
        if not self.var.get():
            self._showing_placeholder = True
            self.entry.configure(style="TEntry")
            self.entry.insert(0, self._placeholder)
            self.entry.configure(foreground=theme.active_palette()["text_secondary"])
        else:
            self.entry.configure(foreground=theme.active_palette()["text"])

    def _on_focus_in(self, _event=None) -> None:
        if self._showing_placeholder:
            self.entry.delete(0, "end")
            self._showing_placeholder = False
            self.entry.configure(foreground=theme.active_palette()["text"])

    def _on_focus_out(self, _event=None) -> None:
        if not self.var.get():
            self._apply_placeholder()

    def _on_write(self, *_args) -> None:
        text = self.var.get()
        if self._showing_placeholder:
            # The placeholder is written directly into the entry; only a
            # real (different) value means the placeholder is gone.
            if not text or text == self._placeholder:
                return
            self._showing_placeholder = False
            self.entry.configure(foreground=theme.active_palette()["text"])
        if text:
            self._clear.grid()
        else:
            self._clear.grid_remove()
        if self._on_change:
            self._on_change(text)

    def set(self, text: str) -> None:
        """Set the search text programmatically (bypassing the placeholder)."""
        self._showing_placeholder = False
        self.entry.configure(foreground=theme.active_palette()["text"])
        self.var.set(text)

    def value(self) -> str:
        return "" if self._showing_placeholder else self.var.get().strip()

    def clear(self) -> None:
        self.var.set("")
        self.entry.delete(0, "end")
        self._showing_placeholder = False
        self._clear.grid_remove()
        try:
            focused = self.entry.focus_get() is self.entry
        except Exception:
            focused = False
        if not focused:
            self._on_focus_out()
        if self._on_change:
            self._on_change("")

    def focus_entry(self) -> None:
        self.entry.focus_set()


class ScrollableFrame(ttk.Frame):
    """A canvas + scrollbar host for long settings-style pages."""

    THEME_AWARE = True

    def __init__(self, parent, bg_role: str = "bg", auto_hide: bool = False,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._bg_role = bg_role
        self._auto_hide = auto_hide

        palette = theme.active_palette()
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0,
                                bg=palette[bg_role], takefocus=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical",
                                       command=self.canvas.yview,
                                       style="Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.body = ttk.Frame(
            self.canvas,
            style="Surface.TFrame" if bg_role == "surface" else "TFrame",
        )
        self._window = self.canvas.create_window((0, 0), window=self.body,
                                                 anchor="nw")
        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # Bind only while the pointer is inside this scroll area.
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)
        self._wheel_bound = False

    def _on_body_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._sync_scrollbar()

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self._sync_scrollbar()

    def _sync_scrollbar(self) -> None:
        # Keep the scroll region current even if a page rebinds <Configure>
        # on ``body`` (Tkinter replaces a binding unless add="+" is used).
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)
        if not self._auto_hide:
            return
        content_h = (bbox[3] - bbox[1]) if bbox else 0
        needed = content_h > self.canvas.winfo_height() + tokens.sc(4)
        if needed:
            self.scrollbar.grid()
        else:
            self.scrollbar.grid_remove()

    def _bind_wheel(self, _event=None) -> None:
        if self._wheel_bound:
            return
        self._wheel_bound = True
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _event=None) -> None:
        if not self._wheel_bound:
            return
        self._wheel_bound = False
        try:
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        except tk.TclError:
            pass

    def _on_wheel(self, event) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-2, "units")
        else:
            self.canvas.yview_scroll(2, "units")

    def apply_theme(self, palette: dict) -> None:
        self.canvas.configure(bg=palette[self._bg_role])


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------

class ToolTip:
    """Hover tooltip with a fixed delay; follows live theme colours."""

    _active: Optional["ToolTip"] = None

    def __init__(self, widget, text: Callable[[], str] | str,
                 delay: int = 450, wraplength: int = 520):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self._after_id: Optional[str] = None
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
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
        try:
            content = self.text() if callable(self.text) else self.text
        except Exception:
            return
        if not content:
            return
        self._hide()
        if ToolTip._active is not None:
            ToolTip._active._hide()
        ToolTip._active = self
        p = theme.active_palette()
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except Exception:
            pass
        label = tk.Label(
            tip, text=content, justify="left",
            background=p["tooltip_bg"], foreground=p["tooltip_fg"],
            highlightthickness=1, highlightbackground=p["tooltip_border"],
            padx=sp("sm"), pady=sp("xs"), font=theme.font("small"),
            wraplength=tokens.sc(self.wraplength),
        )
        label.pack()
        tip.update_idletasks()
        x = self.widget.winfo_rootx() + sp("sm")
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + sp("xs")
        screen_w = self.widget.winfo_screenwidth()
        screen_h = self.widget.winfo_screenheight()
        width = tip.winfo_width()
        height = tip.winfo_height()
        x = max(4, min(x, screen_w - width - 8))
        if y + height > screen_h - 8:
            y = self.widget.winfo_rooty() - height - sp("xs")
        tip.wm_geometry(f"+{x}+{max(4, y)}")
        self._tip = tip

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None
        if ToolTip._active is self:
            ToolTip._active = None


def make_tooltip(widget, text) -> ToolTip:
    return ToolTip(widget, text)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

class Table(ttk.Frame):
    """A themed Treeview with zebra rows, hover, empty state and batching."""

    THEME_AWARE = True

    def __init__(self, parent, columns: Sequence[tuple[str, str, int, str]],
                 height: int = 8, on_activate: Optional[Callable[[], None]] = None,
                 on_select: Optional[Callable[[], None]] = None,
                 empty_text: str = "", bg_role: str = "surface"):
        super().__init__(parent, style="FocusBorder.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._columns = list(columns)
        self._empty_text = empty_text
        self._last_width = 0
        # Do not let fixed Treeview columns dictate the parent's width. The
        # table takes whatever the page gives it and re-proportions columns
        # from that width, so shrinking the window never clips the page.
        natural_height = tokens.sc(tokens.ROW_HEIGHT) * height + tokens.sc(40)
        self.configure(width=tokens.sc(1), height=natural_height)
        self.grid_propagate(False)

        self.tree = ttk.Treeview(
            self, columns=[c[0] for c in columns], show="headings",
            selectmode="browse", height=height,
        )
        # ids are stable; headings/widths come from the column tuples.
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=0, stretch=False)
        for col_id, heading, width, anchor in columns:
            self.tree.heading(col_id, text=heading)
            # Start compact so the table never forces its parent wider than
            # the window; _on_resize then distributes the real width.
            self.tree.column(col_id, width=tokens.sc(40), minwidth=tokens.sc(40),
                             anchor=anchor, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview,
                                 style="Vertical.TScrollbar")
        self.vsb.grid(row=0, column=1, sticky="ns")
        # No horizontal scrollbar: columns are re-proportioned to the visible
        # width instead, so every column stays readable at any window size.
        self.tree.configure(yscrollcommand=self._on_yscroll)
        self.bind("<Configure>", self._on_resize)

        theme.configure_tree_tags(self.tree)
        self._hover_item: Optional[str] = None
        self._cell_text: dict[tuple[str, str], str] = {}
        self._row_values: dict[str, tuple[str, ...]] = {}
        self._empty = ttk.Label(self, text=empty_text,
                                style="SurfaceMuted.TLabel" if bg_role == "surface" else "Muted.TLabel",
                                anchor="center", justify="center")
        self._empty.grid(row=0, column=0, sticky="nsew", padx=sp("lg"))
        self._empty.grid_remove()

        self.tree.bind("<Motion>", self._on_motion)
        self.tree.bind("<Leave>", lambda e: self._clear_hover())
        self.tree.bind("<FocusIn>", lambda e: self.configure(style="FocusBorderOn.TFrame"))
        self.tree.bind("<FocusOut>", lambda e: self.configure(style="FocusBorder.TFrame"))
        if on_activate:
            self.tree.bind("<Double-1>", lambda e: on_activate(), add="+")
            self.tree.bind("<Return>", lambda e: on_activate(), add="+")
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda e: on_select(), add="+")
        ToolTip(self.tree, self._tooltip_text, delay=700)

    def _on_yscroll(self, first, last) -> None:
        """Show the scrollbar only when rows actually overflow."""
        try:
            if float(first) <= 0.0 and float(last) >= 1.0:
                self.vsb.grid_remove()
            else:
                self.vsb.grid()
        except (tk.TclError, ValueError):  # pragma: no cover - destroyed
            return
        self.vsb.set(first, last)

    def _on_resize(self, event) -> None:
        """Re-proportion columns so the table never needs sideways scrolling."""
        scroll = self.vsb.winfo_width() if self.vsb.winfo_ismapped() else 0
        width = int(event.width) - scroll - tokens.sc(2)
        if width <= 1 or abs(width - self._last_width) < 2:
            return
        self._last_width = width
        designs = [max(1, tokens.sc(c[2])) for c in self._columns]
        total = sum(designs)
        remaining = width
        for index, column in enumerate(self._columns):
            if index == len(self._columns) - 1:
                col_width = max(tokens.sc(40), remaining)
            else:
                col_width = max(tokens.sc(40),
                                int(width * designs[index] / total))
                remaining -= col_width
            try:
                self.tree.column(column[0], width=col_width)
            except tk.TclError:  # pragma: no cover - widget destroyed
                return

    # -- data ---------------------------------------------------------
    def clear(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._cell_text.clear()
        self._row_values.clear()
        self._hover_item = None
        self._update_empty()

    def set_empty(self, text: str) -> None:
        self._empty_text = text
        self._empty.configure(text=text)
        self._update_empty()

    def _update_empty(self) -> None:
        if self.tree.get_children():
            self._empty.grid_remove()
        else:
            self._empty.grid()

    def insert_row(self, values: Sequence[str], tags: Sequence[str] = (),
                   iid: Optional[str] = None,
                   cell_text: Optional[dict[str, str]] = None) -> str:
        formatted = [str(v) for v in values]
        item = self.tree.insert("", "end", iid=iid, values=formatted,
                                tags=tuple(tags))
        self._row_values[item] = tuple(formatted)
        for col, text in (cell_text or {}).items():
            self._cell_text[(item, col)] = text
        # Checking ``get_children()`` on every insert makes populating 10k
        # rows quadratic. Only the first row changes the empty state.
        if len(self._row_values) == 1:
            self._update_empty()
        return item

    def insert_batched(self, rows: Iterable[Sequence[str]],
                       tags_for: Optional[Callable[[int], Sequence[str]]] = None,
                       batch_size: int = 250,
                       on_done: Optional[Callable[[], None]] = None) -> None:
        """Insert rows in chunks so the UI stays responsive on 10k files."""
        iterator = iter(enumerate(rows))

        def pump(remaining: int = batch_size) -> None:
            try:
                if not self.winfo_exists():
                    return
            except tk.TclError:
                return
            inserted = 0
            while inserted < remaining:
                try:
                    index, values = next(iterator)
                except StopIteration:
                    self._update_empty()
                    if on_done:
                        on_done()
                    return
                tags = tags_for(index) if tags_for else ()
                self.insert_row(values, tags=tags)
                inserted += 1
            self.after(1, lambda: pump(batch_size))

        pump()

    def selection(self) -> tuple[str, ...]:
        return self.tree.selection()

    def selected_index(self) -> Optional[int]:
        selected = self.tree.selection()
        if not selected:
            return None
        try:
            return self.tree.index(selected[0])
        except tk.TclError:
            return None

    def select_index(self, index: int) -> None:
        children = self.tree.get_children()
        if 0 <= index < len(children):
            self.tree.selection_set(children[index])
            self.tree.focus(children[index])
            self.tree.see(children[index])

    def row_count(self) -> int:
        return len(self.tree.get_children())

    def update_row(self, item: str, values: Sequence[str],
                   tags: Optional[Sequence[str]] = None) -> None:
        try:
            self.tree.item(item, values=[str(v) for v in values])
            if tags is not None:
                self.tree.item(item, tags=tuple(tags))
            self._row_values[item] = tuple(str(v) for v in values)
        except tk.TclError:
            pass

    # -- hover / tooltip ---------------------------------------------
    def _on_motion(self, event) -> None:
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if item == self._hover_item:
            return
        self._clear_hover()
        if item:
            current = list(self.tree.item(item, "tags"))
            if "hover" not in current:
                self.tree.item(item, tags=tuple(current + ["hover"]))
            self._hover_item = item
        _ = column

    def _clear_hover(self) -> None:
        if self._hover_item:
            try:
                tags = [t for t in self.tree.item(self._hover_item, "tags") if t != "hover"]
                self.tree.item(self._hover_item, tags=tuple(tags))
            except tk.TclError:
                pass
            self._hover_item = None

    def _tooltip_text(self) -> str:
        try:
            x, y = self.tree.winfo_pointerxy()
            x -= self.tree.winfo_rootx()
            y -= self.tree.winfo_rooty()
            item = self.tree.identify_row(y)
            column = self.tree.identify_column(x)
            if not item or not column or not column.startswith("#"):
                return ""
            index = int(column[1:]) - 1
            if index < 0 or index >= len(self._columns):
                return ""
            col_id = self._columns[index][0]
            return self._cell_text.get((item, col_id), "")
        except Exception:
            return ""

    def apply_theme(self, palette: dict) -> None:
        theme.configure_tree_tags(self.tree, palette)


# ---------------------------------------------------------------------------
# Modal dialogs
# ---------------------------------------------------------------------------

class Dialog(tk.Toplevel):
    """Base modal dialog: centered, Escape cancels, Enter confirms."""

    def __init__(self, app, title: str, width: int = 560, height: int = 0,
                 dismissible: bool = True):
        super().__init__(app.root)
        self.app = app
        self.result = False
        self.withdraw()
        self.title(title)
        self.configure(bg=app.palette["bg"])
        self.transient(app.root)
        self.resizable(False, False)
        self._dismissible = dismissible
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        try:
            self.iconbitmap(default=str(app.root.iconbitmap()))
        except Exception:
            pass

        self.outer = ttk.Frame(self, style="TFrame", padding=(sp("xl"), sp("lg")))
        self.outer.pack(fill="both", expand=True)
        self.outer.columnconfigure(0, weight=1)
        self.header = ttk.Frame(self.outer, style="TFrame")
        self.header.grid(row=0, column=0, sticky="ew", pady=(0, sp("sm")))
        self.header.columnconfigure(0, weight=1)
        ttk.Label(self.header, text=title, style="Title.TLabel").grid(
            row=0, column=0, sticky="w")
        self.body = ttk.Frame(self.outer, style="TFrame")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.footer = ttk.Frame(self.outer, style="TFrame")
        self.footer.grid(row=2, column=0, sticky="ew", pady=(sp("lg"), 0))

        self.bind("<Escape>", lambda e: self.cancel())
        self.bind("<Return>", lambda e: self.confirm())
        self._width = width
        self._height = height
        self._center()

    def _center(self) -> None:
        self.update_idletasks()
        width = max(self._width, self.winfo_reqwidth())
        height = self._height or self.winfo_reqheight()
        root = self.app.root
        x = root.winfo_rootx() + max(0, (root.winfo_width() - width) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - height) // 2)
        # Keep the dialog on-screen even if the window is near an edge.
        x = max(0, min(x, self.winfo_screenwidth() - width - 8))
        y = max(0, min(y, self.winfo_screenheight() - height - 40))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def add_primary(self, text: str, command: Optional[Callable] = None,
                    style: str = "Primary.TButton") -> ttk.Button:
        button = ttk.Button(self.footer, text=text,
                            command=command or self.confirm, style=style)
        button.pack(side="right")
        self._primary = button
        return button

    def add_secondary(self, text: str, command: Optional[Callable] = None,
                      style: str = "Secondary.TButton") -> ttk.Button:
        button = ttk.Button(self.footer, text=text,
                            command=command or self.cancel, style=style)
        button.pack(side="right", padx=(0, sp("sm")))
        return button

    def confirm(self) -> None:
        self.result = True
        self._close()

    def cancel(self) -> None:
        self.result = False
        self._close()

    def _close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def show(self):
        self.deiconify()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window()
        return self.result


class ConfirmDialog(Dialog):
    """Confirmation with a plain-language summary of what will happen."""

    def __init__(self, app, title: str, message: str, details: str = "",
                 confirm_label: str = "Confirm", danger: bool = False,
                 checkbox: Optional[tuple[str, tk.BooleanVar]] = None):
        super().__init__(app, title, width=620)
        ttk.Label(self.body, text=message, style="Body.TLabel",
                  wraplength=tokens.sc(560), justify="left").grid(
            row=0, column=0, sticky="w")
        if details:
            box = ttk.Frame(self.body, style="Alt.TFrame", padding=sp("md"))
            box.grid(row=1, column=0, sticky="ew", pady=(sp("md"), 0))
            box.columnconfigure(0, weight=1)
            ttk.Label(box, text=details, style="Alt.TLabel",
                      wraplength=tokens.sc(520), justify="left").grid(
                row=0, column=0, sticky="w")
        self.check_var = None
        if checkbox:
            label, self.check_var = checkbox
            ttk.Checkbutton(self.body, text=label, variable=self.check_var,
                            style="TCheckbutton").grid(
                row=2, column=0, sticky="w", pady=(sp("md"), 0))
        self.add_secondary("Cancel")
        style = "Danger.TButton" if danger else "Primary.TButton"
        self.add_primary(confirm_label, style=style)
        self._center()


class ErrorDialog(Dialog):
    """Friendly unexpected-error dialog with copyable technical details."""

    def __init__(self, app, summary: str, details: str):
        super().__init__(app, "Something went wrong", width=620)
        ttk.Label(self.body, text=summary, style="Body.TLabel",
                  wraplength=tokens.sc(560), justify="left").grid(
            row=0, column=0, sticky="w")
        ttk.Label(self.body,
                  text="The action was stopped safely. Nothing was deleted.",
                  style="Muted.TLabel").grid(row=1, column=0, sticky="w",
                                             pady=(sp("sm"), sp("md")))
        text = tk.Text(self.body, height=10, wrap="word", borderwidth=0,
                       highlightthickness=1, font=theme.font(mono=True))
        p = theme.active_palette()
        text.configure(bg=p["surface_sunken"], fg=p["text"],
                       highlightbackground=p["border"], insertbackground=p["text"])
        text.insert("1.0", details)
        text.configure(state="disabled")
        text.grid(row=2, column=0, sticky="nsew")
        self.body.rowconfigure(2, weight=1)
        self.add_secondary("Close", self.cancel)
        self.add_primary("Copy details", self._copy, style="Secondary.TButton")

    def _copy(self) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(self.body.grid_slaves(row=2)[0].get("1.0", "end").strip())
            self.app.toast("Error details copied.", "success")
        except Exception:
            pass


SHORTCUTS = [
    ("Ctrl+1", "Dashboard"),
    ("Ctrl+2", "Organizer"),
    ("Ctrl+3", "Categories & Rules"),
    ("Ctrl+4", "History & Undo"),
    ("Ctrl+5", "Activity"),
    ("Ctrl+6", "Settings"),
    ("Ctrl+F", "Focus the Organizer search box"),
    ("F5", "Refresh the current page"),
    ("Enter", "Preview the folder in the folder field"),
    ("Esc", "Close a dialog / clear search"),
    ("Ctrl+O", "Choose a folder"),
]


class ShortcutsDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Keyboard shortcuts", width=460)
        grid = ttk.Frame(self.body, style="TFrame")
        grid.grid(row=0, column=0, sticky="ew")
        grid.columnconfigure(1, weight=1)
        for row, (key, label) in enumerate(SHORTCUTS):
            ttk.Label(grid, text=key, style="TLabel",
                      font=theme.font("small", "bold")).grid(
                row=row, column=0, sticky="w", pady=sp("xxs"), padx=(0, sp("lg")))
            ttk.Label(grid, text=label, style="Body.TLabel").grid(
                row=row, column=1, sticky="w", pady=sp("xxs"))
        self.add_primary("Close", self.cancel)


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------

class Toast:
    """A transient, non-blocking status message above the status bar."""

    def __init__(self, app, host):
        self.app = app
        self.host = host
        self.frame = ttk.Frame(host, style="BannerInfo.TFrame",
                               padding=(sp("md"), sp("sm")))
        self.label = ttk.Label(self.frame, text="", style="BannerInfo.TLabel",
                               wraplength=tokens.sc(640))
        self.label.pack(side="left")
        self.frame.place_forget()
        self._after: Optional[str] = None
        self._kind = "info"

    def show(self, message: str, kind: str = "info", timeout: int = 5200) -> None:
        self._kind = kind if kind in ("info", "success", "warning", "danger") else "info"
        prefix = {"info": "BannerInfo", "success": "BannerSuccess",
                  "warning": "BannerWarning", "danger": "BannerDanger"}[self._kind]
        self.frame.configure(style=f"{prefix}.TFrame")
        self.label.configure(text=message, style=f"{prefix}.TLabel")
        self.frame.place(relx=0.5, rely=1.0, anchor="s",
                         y=-tokens.sc(12) - tokens.sc(tokens.STATUS_HEIGHT))
        try:
            self.frame.lift()
        except tk.TclError:
            pass
        if self._after:
            try:
                self.host.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.host.after(timeout, self.hide)

    def hide(self) -> None:
        try:
            self.frame.place_forget()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# Backwards-compatible helpers still used by older scripts
# ---------------------------------------------------------------------------

def clear_tree(tree: ttk.Treeview) -> None:
    for item in tree.get_children():
        tree.delete(item)


def set_tree_columns(tree: ttk.Treeview, columns: list[tuple[str, int, str]]) -> None:
    tree.configure(columns=[c[0] for c in columns])
    tree.heading("#0", text="")
    tree.column("#0", width=0, stretch=False)
    for col_id, width, anchor in columns:
        tree.heading(col_id, text=col_id)
        tree.column(col_id, width=tokens.sc(width), anchor=anchor,
                    stretch=(anchor == "w"))


def bind_treeview_shortcuts(tree: ttk.Treeview, on_activate: Callable[[], None]) -> None:
    tree.bind("<Double-1>", lambda e: on_activate(), add="+")
    tree.bind("<Return>", lambda e: on_activate(), add="+")
