"""Generate the EzSort application icon (packaging/ezsort.ico) with Pillow.

Usage:  python scripts/make_icon.py
Produces a multi-resolution .ico (16/32/48/64/128/256 px) showing a rounded
indigo tile with a white "sort" glyph (three bars funneling into a tray).
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "packaging" / "ezsort.ico"
SIZES = (16, 32, 48, 64, 128, 256)


def _draw_icon(size: int) -> Image.Image:
    """Render one square icon frame at ``size`` pixels."""
    s = size / 256.0  # scale factor from the 256px design grid
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded indigo tile with a subtle vertical gradient.
    pad = max(1, int(8 * s))
    radius = max(2, int(48 * s))
    top = (99, 102, 241)      # indigo-500
    bottom = (67, 56, 202)    # indigo-700
    for i in range(radius):  # cheap gradient: stack rounded rects
        t = i / max(1, radius - 1)
        color = tuple(
            int(top[c] + (bottom[c] - top[c]) * t) for c in range(3)
        ) + (255,)
        inset = i
        d.rounded_rectangle(
            [pad + inset, pad, size - pad - inset, size - pad],
            radius=max(1, radius - inset),
            fill=color,
        )

    # White "sort" glyph: three bars of decreasing width above a tray.
    white = (255, 255, 255, 255)
    bar_h = max(2, int(20 * s))
    gap = max(1, int(14 * s))
    cx = size // 2
    widths = (int(140 * s), int(100 * s), int(60 * s))
    y = int(58 * s)
    for w in widths:
        d.rounded_rectangle(
            [cx - w // 2, y, cx + w // 2, y + bar_h],
            radius=max(1, bar_h // 2),
            fill=white,
        )
        y += bar_h + gap

    # Tray / inbox at the bottom.
    tray_top = y + int(6 * s)
    tray_h = max(3, int(46 * s))
    tray_w = int(150 * s)
    d.rounded_rectangle(
        [cx - tray_w // 2, tray_top, cx + tray_w // 2, tray_top + tray_h],
        radius=max(2, int(14 * s)),
        outline=white,
        width=max(2, int(10 * s)),
    )
    # Down-arrow entering the tray (ties bars to the tray visually).
    stem_w = max(2, int(12 * s))
    arrow_y = tray_top - int(4 * s)
    d.rounded_rectangle(
        [cx - stem_w // 2, y - int(4 * s), cx + stem_w // 2, arrow_y],
        radius=max(1, stem_w // 2),
        fill=white,
    )
    return img


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [_draw_icon(s) for s in SIZES]
    frames[-1].save(
        OUT,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=frames[:-1],
    )
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
