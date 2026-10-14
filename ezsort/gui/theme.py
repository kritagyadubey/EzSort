"""Theme: color palettes, fonts and ttk styling for the EzSort app."""

from __future__ import annotations

from tkinter import ttk

DARK = {
    "name": "dark",
    "bg": "#0e1116",
    "surface": "#161b22",
    "surface_alt": "#1c2230",
    "border": "#2a3140",
    "text": "#e6edf3",
    "muted": "#9aa4b2",
    "accent": "#58a6ff",
    "accent_hover": "#79b8ff",
    "accent_active": "#3d8bfd",
    "success": "#3fb950",
    "warning": "#d29922",
    "danger": "#f85149",
    "selection": "#1f3a5f",
    "row_alt": "#131820",
    "sidebar": "#10141b",
    "on_accent": "#0b1220",
}

LIGHT = {
    "name": "light",
    "bg": "#f4f6f9",
    "surface": "#ffffff",
    "surface_alt": "#eef1f5",
    "border": "#d6dbe3",
    "text": "#1c2430",
    "muted": "#5f6b7d",
    "accent": "#0969da",
    "accent_hover": "#0a6ccd",
    "accent_active": "#085fbd",
    "success": "#1a7f37",
    "warning": "#9a6700",
    "danger": "#cf222e",
    "selection": "#dbe9fb",
    "row_alt": "#f6f8fa",
    "sidebar": "#eaeef3",
    "on_accent": "#ffffff",
}

PALETTES = {"dark": DARK, "light": LIGHT}

FONT_FAMILY = "Segoe UI"
BASE_SIZE = 10


def get_palette(name: str | None) -> dict:
    """Return the palette dict for *name* (defaults to dark)."""
    if isinstance(name, str) and name.lower() in PALETTES:
        return PALETTES[name.lower()]
    return DARK


def apply_styles(root, palette: dict) -> None:
    """Apply ttk styles for the given palette to *root*."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:  # pragma: no cover
        pass

    p = palette
    f = FONT_FAMILY

    style.configure(".", background=p["bg"], foreground=p["text"],
                    fieldbackground=p["surface"], bordercolor=p["border"])
    style.configure("TFrame", background=p["bg"])
    style.configure("Surface.TFrame", background=p["surface"])
    style.configure("Alt.TFrame", background=p["surface_alt"])
    style.configure("Sidebar.TFrame", background=p["sidebar"])
    style.configure("TLabel", background=p["bg"], foreground=p["text"],
                    font=(f, BASE_SIZE))
    style.configure("Surface.TLabel", background=p["surface"], foreground=p["text"],
                    font=(f, BASE_SIZE))
    style.configure("Alt.TLabel", background=p["surface_alt"], foreground=p["text"],
                    font=(f, BASE_SIZE))
    style.configure("Title.TLabel", background=p["bg"], foreground=p["text"],
                    font=(f, 17, "bold"))
    style.configure("CardTitle.TLabel", background=p["surface"], foreground=p["text"],
                    font=(f, 13, "bold"))
    style.configure("Subtitle.TLabel", background=p["bg"], foreground=p["muted"],
                    font=(f, 10))
    style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"],
                    font=(f, 9))
    style.configure("SurfaceMuted.TLabel", background=p["surface"], foreground=p["muted"],
                    font=(f, 9))
    style.configure("Stat.TLabel", background=p["surface"], foreground=p["text"],
                    font=(f, 22, "bold"))
    style.configure("StatCaption.TLabel", background=p["surface"], foreground=p["muted"],
                    font=(f, 9))
    style.configure("Success.TLabel", background=p["bg"], foreground=p["success"],
                    font=(f, 10))
    style.configure("Danger.TLabel", background=p["bg"], foreground=p["danger"],
                    font=(f, 10))
    style.configure("SurfaceDanger.TLabel", background=p["surface"], foreground=p["danger"],
                    font=(f, 10))
    style.configure("SurfaceSuccess.TLabel", background=p["surface"], foreground=p["success"],
                    font=(f, 10))

    # Buttons
    style.configure("TButton", background=p["surface_alt"], foreground=p["text"],
                    font=(f, 10), padding=(14, 7), borderwidth=1,
                    focusthickness=1, focuscolor=p["accent"])
    style.map("TButton",
              background=[("active", p["border"]), ("pressed", p["selection"])],
              foreground=[("disabled", p["muted"])])

    style.configure("Accent.TButton", background=p["accent"], foreground=p["on_accent"],
                    font=(f, 10, "bold"), padding=(16, 7), borderwidth=0)
    style.map("Accent.TButton",
              background=[("active", p["accent_hover"]), ("pressed", p["accent_active"]),
                          ("disabled", p["border"])],
              foreground=[("disabled", p["muted"])])

    style.configure("Danger.TButton", background=p["surface_alt"], foreground=p["danger"],
                    font=(f, 10), padding=(14, 7), borderwidth=1)
    style.map("Danger.TButton",
              background=[("active", p["border"])],
              foreground=[("disabled", p["muted"])])

    # Inputs
    style.configure("TEntry", fieldbackground=p["surface"], foreground=p["text"],
                    insertcolor=p["text"], borderwidth=1, padding=(8, 6))
    style.map("TEntry", bordercolor=[("focus", p["accent"])])

    style.configure("TCombobox", fieldbackground=p["surface"], foreground=p["text"],
                    background=p["surface_alt"], arrowcolor=p["text"], padding=(8, 6))
    style.map("TCombobox",
              fieldbackground=[("readonly", p["surface"])],
              foreground=[("readonly", p["text"])],
              selectbackground=[("readonly", p["surface"])],
              selectforeground=[("readonly", p["text"])])

    style.configure("TCheckbutton", background=p["bg"], foreground=p["text"],
                    font=(f, 10), padding=(0, 3))
    style.map("TCheckbutton",
              background=[("active", p["bg"])],
              foreground=[("disabled", p["muted"])])

    style.configure("Surface.TCheckbutton", background=p["surface"], foreground=p["text"],
                    font=(f, 10), padding=(0, 3))
    style.map("Surface.TCheckbutton", background=[("active", p["surface"])])

    style.configure("TRadiobutton", background=p["surface"], foreground=p["text"],
                    font=(f, 10), padding=(0, 3))
    style.map("TRadiobutton", background=[("active", p["surface"])])

    style.configure("TLabelframe", background=p["bg"], foreground=p["muted"],
                    font=(f, 10, "bold"), borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", background=p["bg"], foreground=p["muted"],
                    font=(f, 10, "bold"))

    style.configure("TSeparator", background=p["border"])
    style.configure("TSpinbox", arrowsize=14, padding=(8, 6))

    # Progress
    style.configure("TProgressbar", background=p["accent"], troughcolor=p["surface_alt"],
                    borderwidth=0, thickness=8)

    # Treeview (tables)
    style.configure("Treeview",
                    background=p["surface"],
                    fieldbackground=p["surface"],
                    foreground=p["text"],
                    font=(f, 10),
                    rowheight=28,
                    borderwidth=0)
    style.configure("Treeview.Heading",
                    background=p["surface_alt"],
                    foreground=p["muted"],
                    font=(f, 9, "bold"),
                    relief="flat",
                    padding=(8, 7))
    style.map("Treeview",
              background=[("selected", p["selection"])],
              foreground=[("selected", p["text"])])
    style.map("Treeview.Heading", background=[("active", p["border"])])

    # Vertical scrollbar
    style.configure("Vertical.TScrollbar",
                    background=p["surface_alt"],
                    troughcolor=p["bg"],
                    bordercolor=p["bg"],
                    arrowcolor=p["muted"])
    style.map("Vertical.TScrollbar",
              background=[("active", p["border"])])

    # Segmented / small buttons used in toolbars
    style.configure("Small.TButton", font=(f, 9), padding=(10, 5))
    style.configure("SmallAccent.TButton", background=p["accent"],
                    foreground=p["on_accent"], font=(f, 9, "bold"),
                    padding=(12, 5), borderwidth=0)
    style.map("SmallAccent.TButton",
              background=[("active", p["accent_hover"]), ("pressed", p["accent_active"]),
                          ("disabled", p["border"])],
              foreground=[("disabled", p["muted"])])


def short_path(path: str, max_length: int = 64) -> str:
    """Shorten a long path for display, keeping the tail visible."""
    text = str(path)
    if len(text) <= max_length:
        return text
    head = max_length - 12
    return text[:head] + "..." + text[-(max_length - head - 3):]
