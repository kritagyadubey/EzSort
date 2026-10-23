"""Programmatic line-icon set (no emoji, no remote assets, no font deps).

Every icon is drawn on a Tk canvas from a normalised 24x24 design grid
with the same stroke width, cap and join style, so the set stays visually
consistent at every DPI scale. ``draw_icon`` is the only entry point used
by the rest of the app.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import Callable

SIZE = 18
STROKE = 1.7
_FALLBACK = "#888888"

IconPainter = Callable[[tk.Canvas, float, float, str, float], None]


def _xy(c: tk.Canvas, pts: list[float], pad: float, span: float, color: str,
        width: float, *, closed: bool = False, fill: str = "") -> None:
    coords = [pad + v * span for v in pts]
    c.create_line(*coords, fill=color, width=width, capstyle="round",
                  joinstyle="round", smooth=False)
    if closed:
        c.create_line(coords[-2], coords[-1], coords[0], coords[1],
                      fill=color, width=width, capstyle="round")


def _home(c, pad, span, color, w):
    _xy(c, [3, 11, 12, 3, 21, 11], pad, span, color, w)
    _xy(c, [5.5, 10, 5.5, 20.5, 18.5, 20.5, 18.5, 10], pad, span, color, w)
    _xy(c, [10, 20.5, 10, 14.5, 14, 14.5, 14, 20.5], pad, span, color, w)


def _folder(c, pad, span, color, w):
    _xy(c, [3, 6.5, 3, 19, 21, 19, 21, 8.5, 12, 8.5, 10, 6.5, 3, 6.5],
        pad, span, color, w)


def _tag(c, pad, span, color, w):
    _xy(c, [3.5, 3.5, 11, 3.5, 20.5, 13, 13, 20.5, 3.5, 11, 3.5, 3.5],
        pad, span, color, w)
    cx, cy, r = pad + 7.6 * span, pad + 7.6 * span, max(1.0, 1.3 * span)
    c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=w)


def _clock(c, pad, span, color, w):
    _oval(c, pad, span, 3.5, 3.5, 20.5, 20.5, color, w)
    _xy(c, [12, 7, 12, 12, 15.8, 14.2], pad, span, color, w)


def _pulse(c, pad, span, color, w):
    _xy(c, [2.5, 12, 7, 12, 9.3, 6, 13.4, 18.5, 16, 12, 21.5, 12],
        pad, span, color, w)


def _gear(c, pad, span, color, w):
    r1, r2 = 9.2, 6.7
    cx = cy = 12.0
    for i in range(8):
        a = math.radians(i * 45)
        _xy(c, [cx + r2 * math.cos(a), cy + r2 * math.sin(a),
                cx + r1 * math.cos(a), cy + r1 * math.sin(a)],
            pad, span, color, w)
    _oval(c, pad, span, 7.2, 7.2, 16.8, 16.8, color, w)
    _oval(c, pad, span, 10.4, 10.4, 13.6, 13.6, color, w)


def _search(c, pad, span, color, w):
    _oval(c, pad, span, 4, 4, 15.5, 15.5, color, w)
    _xy(c, [14.2, 14.2, 20, 20], pad, span, color, w)


def _close(c, pad, span, color, w):
    _xy(c, [6, 6, 18, 18], pad, span, color, w)
    _xy(c, [18, 6, 6, 18], pad, span, color, w)


def _check(c, pad, span, color, w):
    _xy(c, [4.5, 12.5, 9.5, 17.5, 19.5, 6.5], pad, span, color, w)


def _alert(c, pad, span, color, w):
    _xy(c, [12, 3.5, 21, 20, 3, 20, 12, 3.5], pad, span, color, w)
    _xy(c, [12, 9, 12, 14], pad, span, color, w)
    cx, cy, r = pad + 12 * span, pad + 17.2 * span, max(0.8, 0.7 * span)
    c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline=color)


def _info(c, pad, span, color, w):
    _oval(c, pad, span, 3.5, 3.5, 20.5, 20.5, color, w)
    _xy(c, [12, 11, 12, 16.5], pad, span, color, w)
    cx, cy, r = pad + 12 * span, pad + 7.8 * span, max(0.8, 0.7 * span)
    c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline=color)


def _success(c, pad, span, color, w):
    _oval(c, pad, span, 3.5, 3.5, 20.5, 20.5, color, w)
    _xy(c, [7.5, 12.2, 10.8, 15.5, 16.8, 9], pad, span, color, w)


def _undo(c, pad, span, color, w):
    _xy(c, [8.5, 7, 3.5, 11.5, 8.5, 16], pad, span, color, w)
    _xy(c, [3.5, 11.5, 14, 11.5], pad, span, color, w)
    c.create_arc(pad + 8 * span, pad + 4.5 * span, pad + 21 * span,
                 pad + 17 * span, start=270, extent=150, style="arc",
                 outline=color, width=w)


def _plus(c, pad, span, color, w):
    _xy(c, [12, 5, 12, 19], pad, span, color, w)
    _xy(c, [5, 12, 19, 12], pad, span, color, w)


def _edit(c, pad, span, color, w):
    _xy(c, [4, 20, 5, 15.5, 16, 4.5, 19.5, 8, 8.5, 19, 4, 20],
        pad, span, color, w)
    _xy(c, [14.5, 6, 18, 9.5], pad, span, color, w)


def _trash(c, pad, span, color, w):
    _xy(c, [4, 6.5, 20, 6.5], pad, span, color, w)
    _xy(c, [9.5, 6.5, 9.5, 3.5, 14.5, 3.5, 14.5, 6.5], pad, span, color, w)
    _xy(c, [6, 6.5, 7, 21, 17, 21, 18, 6.5], pad, span, color, w)
    _xy(c, [10, 10, 10, 17.5], pad, span, color, w)
    _xy(c, [14, 10, 14, 17.5], pad, span, color, w)


def _chevron(c, pad, span, color, w):
    _xy(c, [8, 10.5, 12, 14.5, 16, 10.5], pad, span, color, w)


def _arrow_up(c, pad, span, color, w):
    _xy(c, [12, 19, 12, 5], pad, span, color, w)
    _xy(c, [6.5, 10.5, 12, 5, 17.5, 10.5], pad, span, color, w)


def _arrow_down(c, pad, span, color, w):
    _xy(c, [12, 5, 12, 19], pad, span, color, w)
    _xy(c, [6.5, 13.5, 12, 19, 17.5, 13.5], pad, span, color, w)


def _copy(c, pad, span, color, w):
    _xy(c, [8.5, 8.5, 20, 8.5, 20, 20, 8.5, 20, 8.5, 8.5],
        pad, span, color, w)
    _xy(c, [5.5, 15.5, 4, 15.5, 4, 4, 15.5, 4, 15.5, 5.5],
        pad, span, color, w)


def _refresh(c, pad, span, color, w):
    c.create_arc(pad + 4 * span, pad + 4 * span, pad + 20 * span,
                 pad + 20 * span, start=35, extent=285, style="arc",
                 outline=color, width=w)
    _xy(c, [17.5, 4.5, 20.2, 9.2, 15.2, 9.8], pad, span, color, w)


def _sort(c, pad, span, color, w):
    _xy(c, [4, 7, 20, 7], pad, span, color, w)
    _xy(c, [4, 12, 15, 12], pad, span, color, w)
    _xy(c, [4, 17, 10, 17], pad, span, color, w)


def _shield(c, pad, span, color, w):
    _xy(c, [12, 3.5, 20, 6.5, 20, 12], pad, span, color, w)
    c.create_arc(pad + 4 * span, pad + 8 * span, pad + 20 * span,
                 pad + 24 * span, start=180, extent=180, style="arc",
                 outline=color, width=w)
    _xy(c, [20, 12, 20, 13.5], pad, span, color, w)
    _xy(c, [4, 12, 4, 13.5], pad, span, color, w)
    _xy(c, [4, 13.5, 12, 20.5, 20, 13.5], pad, span, color, w)
    _xy(c, [9, 12, 11, 14, 15.5, 9.5], pad, span, color, w)


def _external(c, pad, span, color, w):
    _xy(c, [13, 4, 20, 4, 20, 11], pad, span, color, w)
    _xy(c, [20, 4, 11.5, 12.5], pad, span, color, w)
    _xy(c, [18, 14, 18, 20, 4, 20, 4, 6, 10, 6], pad, span, color, w)


def _folder_open(c, pad, span, color, w):
    _xy(c, [3, 6.5, 3, 19, 21, 19, 21, 8.5, 12, 8.5, 10, 6.5, 3, 6.5],
        pad, span, color, w)
    _xy(c, [3, 11, 21, 11], pad, span, color, w)


def _oval(c, pad, span, x1, y1, x2, y2, color, w):
    c.create_oval(pad + x1 * span, pad + y1 * span, pad + x2 * span,
                  pad + y2 * span, outline=color, width=w)


ICONS: dict[str, IconPainter] = {
    "dashboard": _home,
    "organizer": _folder,
    "categories": _tag,
    "history": _clock,
    "activity": _pulse,
    "settings": _gear,
    "search": _search,
    "close": _close,
    "check": _check,
    "alert": _alert,
    "info": _info,
    "success": _success,
    "undo": _undo,
    "plus": _plus,
    "edit": _edit,
    "trash": _trash,
    "chevron_down": _chevron,
    "arrow_up": _arrow_up,
    "arrow_down": _arrow_down,
    "copy": _copy,
    "refresh": _refresh,
    "sort": _sort,
    "shield": _shield,
    "external": _external,
    "folder": _folder_open,
}

ICON_NAMES: tuple[str, ...] = tuple(ICONS)


def draw_icon(canvas: tk.Canvas, name: str, color: str, size: int = SIZE,
              width: float = STROKE) -> None:
    """Draw the named icon centred in a square canvas."""
    canvas.delete("all")
    canvas.configure(width=size, height=size, bg=canvas.cget("bg"))
    painter = ICONS.get(name)
    if painter is None:
        return
    # 24-unit grid scaled into the canvas with a small breathing margin.
    span = (size / 24.0) * 0.86
    pad = size * 0.07
    painter(canvas, pad, span, color or _FALLBACK, width)
