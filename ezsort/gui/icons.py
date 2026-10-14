"""Tiny vector icons drawn on Tk canvases (no font/emoji dependencies)."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

SIZE = 18


def _home(c: tk.Canvas, s: int, color: str) -> None:
    m = s // 6
    c.create_line(m, s // 2, s // 2, m, s - m, s // 2,
                  fill=color, width=1.6, joinstyle="round", capstyle="round")
    c.create_rectangle(m + 1, s // 2, s - m - 1, s - m - 1,
                       outline=color, width=1.6)
    c.create_rectangle(s // 2 - 2, s - m - 4, s // 2 + 2, s - m - 1,
                       outline=color, width=1.4)


def _folder(c: tk.Canvas, s: int, color: str) -> None:
    m = s // 6
    c.create_line(m, s // 3, s // 3, s // 3, s // 2 + 1, m + 2,
                  fill=color, width=1.5, capstyle="round")
    c.create_rectangle(m, s // 3, s - m, s - m,
                       outline=color, width=1.6)


def _tag(c: tk.Canvas, s: int, color: str) -> None:
    m = s // 6
    c.create_polygon(m, m, s // 2 + 2, m, s - m, s // 2, s // 2, s - m,
                     outline=color, fill="", width=1.6, joinstyle="round")
    c.create_oval(m + 2, m + 2, m + 6, m + 6, outline=color, width=1.4)


def _clock(c: tk.Canvas, s: int, color: str) -> None:
    m = s // 6
    c.create_oval(m, m, s - m, s - m, outline=color, width=1.6)
    c.create_line(s // 2, s // 2, s // 2, m + 3, fill=color, width=1.5,
                  capstyle="round")
    c.create_line(s // 2, s // 2, s - m - 3, s // 2 + 2, fill=color, width=1.5,
                  capstyle="round")


def _pulse(c: tk.Canvas, s: int, color: str) -> None:
    m = s // 5
    y = s // 2
    pts = [m, y, m + (s - 2 * m) // 4, y, m + (s - 2 * m) // 3, y - s // 4,
           m + (s - 2 * m) // 2, y + s // 4, m + 3 * (s - 2 * m) // 4, y,
           s - m, y]
    c.create_line(*pts, fill=color, width=1.7, joinstyle="round",
                  capstyle="round")


def _gear(c: tk.Canvas, s: int, color: str) -> None:
    m = s // 5
    c.create_oval(m + 2, m + 2, s - m - 2, s - m - 2, outline=color, width=1.6)
    c.create_oval(s // 2 - 2, s // 2 - 2, s // 2 + 2, s // 2 + 2,
                  outline=color, width=1.3)
    import math

    cx = cy = s / 2
    r1 = s / 2 - m + 1
    r2 = s / 2 - m - 2
    for i in range(8):
        a = math.radians(i * 45)
        c.create_line(cx + r2 * math.cos(a), cy + r2 * math.sin(a),
                      cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                      fill=color, width=1.6, capstyle="round")


ICONS: dict[str, Callable[[tk.Canvas, int, str], None]] = {
    "dashboard": _home,
    "organizer": _folder,
    "categories": _tag,
    "history": _clock,
    "activity": _pulse,
    "settings": _gear,
}


def draw_icon(canvas: tk.Canvas, name: str, color: str, size: int = SIZE) -> None:
    """Draw icon *name* onto *canvas*."""
    canvas.delete("all")
    canvas.configure(width=size, height=size)
    painter = ICONS.get(name)
    if painter:
        painter(canvas, size, color)
