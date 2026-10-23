"""Design tokens: one source of truth for colour, spacing and type.

Pages never hardcode a colour or a pixel value. They read semantic roles
from here (through ``theme.active_palette()``) and spacing/type values from
the scales below. Both themes are designed independently: the light theme
is a warm paper palette, the dark theme a warm-neutral slate, not a
mechanical inversion of the other.

Tk widgets cannot draw rounded corners reliably across platforms, so the
visual language deliberately uses crisp 1px borders and flat surfaces
instead of fake radii. ``RADII`` is kept for icon/illustration drawing.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Spacing / sizing scales (all values are device-independent pixels at 100%)
# ---------------------------------------------------------------------------

SPACE: Final[dict[str, int]] = {
    "xxs": 2,
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
    "xxxl": 40,
}

#: Alias used by pages for readability: SPACING["lg"].
SPACING: Final[dict[str, int]] = SPACE

RADII: Final[dict[str, int]] = {"sm": 4, "md": 8, "lg": 12, "pill": 999}

#: Type scale in points. Keep one size per hierarchy level.
TYPE: Final[dict[str, int]] = {
    "display": 24,
    "h1": 19,
    "h2": 13,
    "body": 10,
    "small": 9,
    "micro": 8,
}

ICON_SIZE: Final[int] = 18
ROW_HEIGHT: Final[int] = 30
CONTROL_HEIGHT: Final[int] = 28
SIDEBAR_WIDTH: Final[int] = 232
STATUS_HEIGHT: Final[int] = 28
MIN_WINDOW: Final[tuple[int, int]] = (1024, 680)
DEFAULT_WINDOW: Final[tuple[int, int]] = (1280, 820)

# ---------------------------------------------------------------------------
# Colour roles
# ---------------------------------------------------------------------------

#: Roles that must exist in every palette. Tests enforce completeness.
COLOR_ROLES: Final[tuple[str, ...]] = (
    "name",
    "bg",
    "surface",
    "surface_alt",
    "surface_sunken",
    "sidebar",
    "border",
    "border_strong",
    "text",
    "text_secondary",
    "text_disabled",
    "accent",
    "accent_hover",
    "accent_pressed",
    "on_accent",
    "success",
    "success_bg",
    "warning",
    "warning_bg",
    "danger",
    "danger_bg",
    "info",
    "info_bg",
    "selection",
    "selection_text",
    "focus",
    "row_alt",
    "tooltip_bg",
    "tooltip_fg",
    "tooltip_border",
)

#: Pairs the contrast test enforces as (foreground, background, minimum).
#: Body text needs 4.5:1; large text and UI boundaries need 3:1 (WCAG AA).
CONTRAST_PAIRS: Final[tuple[tuple[str, str, float], ...]] = (
    ("text", "bg", 4.5),
    ("text", "surface", 4.5),
    ("text", "surface_alt", 4.5),
    ("text", "sidebar", 4.5),
    ("text_secondary", "bg", 4.5),
    ("text_secondary", "surface", 4.5),
    ("text_secondary", "sidebar", 4.5),
    ("text_secondary", "surface_alt", 4.5),
    ("on_accent", "accent", 4.5),
    ("on_accent", "accent_hover", 4.5),
    ("selection_text", "selection", 4.5),
    ("success", "surface", 4.5),
    ("danger", "surface", 4.5),
    ("warning", "surface", 4.5),
    ("info", "surface", 4.5),
    ("success", "success_bg", 3.0),
    ("danger", "danger_bg", 3.0),
    ("warning", "warning_bg", 3.0),
    ("info", "info_bg", 3.0),
    ("border_strong", "surface", 3.0),
    ("focus", "bg", 3.0),
    ("focus", "surface", 3.0),
    ("tooltip_fg", "tooltip_bg", 4.5),
)

# Dark: warm-neutral slate. Not pure black; surfaces step up in lightness.
DARK: Final[dict[str, str]] = {
    "name": "dark",
    "bg": "#14161a",
    "surface": "#1b1e24",
    "surface_alt": "#22262e",
    "surface_sunken": "#101216",
    "sidebar": "#111317",
    "border": "#30353e",
    "border_strong": "#616a78",
    "text": "#e9ebef",
    "text_secondary": "#a9b0bb",
    "text_disabled": "#6e7681",
    "accent": "#2b64c4",
    "accent_hover": "#2f6fdb",
    "accent_pressed": "#2455a8",
    "on_accent": "#ffffff",
    "success": "#54c777",
    "success_bg": "#17301f",
    "warning": "#e2ac45",
    "warning_bg": "#332814",
    "danger": "#f27c72",
    "danger_bg": "#361b1b",
    "info": "#74b0f2",
    "info_bg": "#172a3f",
    "selection": "#233b5e",
    "selection_text": "#f1f5ff",
    "focus": "#8db8ff",
    "row_alt": "#181b20",
    "tooltip_bg": "#2a2f38",
    "tooltip_fg": "#f2f4f7",
    "tooltip_border": "#4c5563",
}

# Light: warm paper. Surfaces are true white, chrome is a soft stone tone.
LIGHT: Final[dict[str, str]] = {
    "name": "light",
    "bg": "#f5f4f0",
    "surface": "#ffffff",
    "surface_alt": "#f0efea",
    "surface_sunken": "#e8e6e0",
    "sidebar": "#ecebe5",
    "border": "#d7d4ca",
    "border_strong": "#8f8a7e",
    "text": "#1c2027",
    "text_secondary": "#545e6d",
    "text_disabled": "#8c939e",
    "accent": "#1f5bd6",
    "accent_hover": "#1a4fba",
    "accent_pressed": "#15439c",
    "on_accent": "#ffffff",
    "success": "#1c7a3d",
    "success_bg": "#e4f3e9",
    "warning": "#855600",
    "warning_bg": "#f9eed7",
    "danger": "#b4232d",
    "danger_bg": "#fbe8e8",
    "info": "#1a5aa8",
    "info_bg": "#e7f0fb",
    "selection": "#dce8fb",
    "selection_text": "#14213a",
    "focus": "#1f5bd6",
    "row_alt": "#faf9f6",
    "tooltip_bg": "#232932",
    "tooltip_fg": "#f4f6f8",
    "tooltip_border": "#3a424d",
}

PALETTES: Final[dict[str, dict[str, str]]] = {"dark": DARK, "light": LIGHT}


# ---------------------------------------------------------------------------
# High-DPI scaling
# ---------------------------------------------------------------------------

_scale: float = 1.0


def set_scale(value: float) -> None:
    """Set the single UI scale factor (1.0 == 100% at 96 DPI)."""
    global _scale
    _scale = max(0.75, min(3.0, float(value)))


def get_scale() -> float:
    return _scale


def scale_from_dpi(dpi: float, override: float | None = None) -> float:
    """Turn a measured DPI into the UI scale (with optional test override)."""
    if override is not None and override > 0:
        return max(0.75, min(3.0, override))
    return max(0.75, min(3.0, dpi / 96.0))


def sc(value: float) -> int:
    """Scale a pixel value from the 100% design grid."""
    return max(1, int(round(value * _scale)))


def font_size_points(key: str) -> int:
    """Type-scale size in *points* (Tk scales points with the display DPI)."""
    return TYPE.get(key, TYPE["body"])
