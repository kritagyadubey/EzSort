"""Theme application: ttk styles, fonts, tables and colour helpers.

All colours come from :mod:`ezsort.gui.tokens`; no page or component may
hardcode a hex value. Sizes are expressed on the 100% design grid and pass
through ``tokens.sc`` so one scale factor controls the whole UI.
"""

from __future__ import annotations

from tkinter import font as tkfont
from tkinter import ttk

from ezsort.gui import tokens
from ezsort.gui.tokens import PALETTES, TYPE

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"
BASE_SIZE = TYPE["body"]

#: Palette last applied to a root window (raw Tk widgets read this).
_ACTIVE_PALETTE: dict = PALETTES["dark"]
_families: set[str] = set()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    text = color.lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def relative_luminance(color: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` colour."""
    channels = []
    for value in _hex_to_rgb(color):
        c = value / 255.0
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colours."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def resolve_families(root) -> None:
    """Pick installed font families once per application."""
    global _families
    try:
        available = set(tkfont.families(root))
    except Exception:  # pragma: no cover - very unusual Tk builds
        available = set()
    _families = available


def family(mono: bool = False) -> str:
    if mono:
        for candidate in (MONO_FAMILY, "Cascadia Mono", "Consolas", "Courier New"):
            if not _families or candidate in _families:
                return candidate
        return "Courier New"
    for candidate in (FONT_FAMILY, "Segoe UI Variable Text", "Helvetica Neue",
                      "DejaVu Sans", "Arial"):
        if not _families or candidate in _families:
            return candidate
    return "TkDefaultFont"


def font(size_key: str = "body", weight: str = "normal", mono: bool = False):
    """Return a Tk font tuple for a type-scale key."""
    return (family(mono), tokens.font_size_points(size_key), weight)


def get_palette(name: str | None) -> dict:
    """Return the palette for *name* (dark when unknown)."""
    if isinstance(name, str) and name.lower() in PALETTES:
        return PALETTES[name.lower()]
    return PALETTES["dark"]


def active_palette() -> dict:
    """Palette last passed to :func:`apply_styles`."""
    return _ACTIVE_PALETTE


def apply_styles(root, palette: dict) -> None:
    """Apply every shared ttk style for *palette* to *root*."""
    global _ACTIVE_PALETTE
    _ACTIVE_PALETTE = palette
    resolve_families(root)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:  # pragma: no cover - platform fallback
        pass

    p = palette
    s = tokens.sc
    body = font("body")
    small = font("small")
    micro = font("micro")
    h1 = font("h1", "bold")
    h2 = font("h2", "bold")
    display = font("display", "bold")

    # ---- base ---------------------------------------------------------
    style.configure(
        ".", background=p["bg"], foreground=p["text"],
        fieldbackground=p["surface"], bordercolor=p["border"],
        lightcolor=p["border"], darkcolor=p["border"],
        troughcolor=p["surface_sunken"], focuscolor=p["focus"],
        selectbackground=p["selection"], selectforeground=p["selection_text"],
        font=body,
    )

    # ---- containers ---------------------------------------------------
    for name, role in (
        ("TFrame", "bg"), ("Surface.TFrame", "surface"),
        ("Alt.TFrame", "surface_alt"), ("Sidebar.TFrame", "sidebar"),
        ("Sunken.TFrame", "surface_sunken"), ("Header.TFrame", "bg"),
    ):
        style.configure(name, background=p[role])

    # ---- labels -------------------------------------------------------
    label_specs = {
        "TLabel": ("bg", "text", body),
        "Display.TLabel": ("bg", "text", display),
        "Title.TLabel": ("bg", "text", h1),
        "CardTitle.TLabel": ("surface", "text", h2),
        "Body.TLabel": ("bg", "text", body),
        "Subtitle.TLabel": ("bg", "text_secondary", body),
        "Muted.TLabel": ("bg", "text_secondary", small),
        "Micro.TLabel": ("bg", "text_secondary", micro),
        "Surface.TLabel": ("surface", "text", body),
        "SurfaceSmall.TLabel": ("surface", "text", small),
        "SurfaceMuted.TLabel": ("surface", "text_secondary", small),
        "SurfaceMicro.TLabel": ("surface", "text_secondary", micro),
        "Alt.TLabel": ("surface_alt", "text", body),
        "Sidebar.TLabel": ("sidebar", "text", body),
        "SidebarMuted.TLabel": ("sidebar", "text_secondary", small),
        "Stat.TLabel": ("surface", "text", display),
        "StatCaption.TLabel": ("surface", "text_secondary", small),
        "Success.TLabel": ("bg", "success", body),
        "SurfaceSuccess.TLabel": ("surface", "success", body),
        "Warning.TLabel": ("bg", "warning", body),
        "SurfaceWarning.TLabel": ("surface", "warning", body),
        "Danger.TLabel": ("bg", "danger", body),
        "SurfaceDanger.TLabel": ("surface", "danger", body),
        "Info.TLabel": ("bg", "info", body),
        "SurfaceInfo.TLabel": ("surface", "info", body),
    }
    for name, (bg_role, fg_role, fnt) in label_specs.items():
        style.configure(name, background=p[bg_role], foreground=p[fg_role],
                        font=fnt)

    # ---- buttons ------------------------------------------------------
    def button(name, bg, fg, hover, pressed, *, bold=False, border=None,
               focus=None):
        style.configure(
            name, background=bg, foreground=fg,
            font=(family(), TYPE["body"], "bold" if bold else "normal"),
            padding=(s(14), s(7)), borderwidth=s(1), relief="flat",
            anchor="center", focusthickness=s(2), focuscolor=focus or p["focus"],
            bordercolor=border or bg, lightcolor=border or bg,
            darkcolor=border or bg,
        )
        style.map(
            name,
            background=[("disabled", p["surface_alt"]), ("pressed", pressed),
                        ("active", hover)],
            foreground=[("disabled", p["text_disabled"])],
            bordercolor=[("focus", focus or p["focus"])],
            lightcolor=[("focus", focus or p["focus"])],
            darkcolor=[("focus", focus or p["focus"])],
        )

    button("TButton", p["surface"], p["text"], p["surface_alt"],
           p["surface_sunken"], border=p["border"])
    button("Secondary.TButton", p["surface"], p["text"], p["surface_alt"],
           p["surface_sunken"], border=p["border"])
    button("Primary.TButton", p["accent"], p["on_accent"], p["accent_hover"],
           p["accent_pressed"], bold=True, border=p["accent"])
    button("Danger.TButton", p["surface"], p["danger"], p["danger_bg"],
           p["surface_sunken"], border=p["border"], focus=p["danger"])
    button("Ghost.TButton", p["bg"], p["text_secondary"], p["surface_alt"],
           p["surface_sunken"], border=p["bg"])
    button("SurfaceGhost.TButton", p["surface"], p["text_secondary"],
           p["surface_alt"], p["surface_sunken"], border=p["surface"])
    button("Link.TButton", p["bg"], p["accent"], p["bg"], p["bg"],
           border=p["bg"])
    style.configure("Link.TButton", padding=(s(2), s(2)))
    style.map("Link.TButton", foreground=[("active", p["accent_hover"]),
                                          ("disabled", p["text_disabled"])])

    style.configure("Small.TButton", padding=(s(10), s(4)), font=font("small"))
    style.configure("SmallPrimary.TButton", padding=(s(10), s(4)),
                    font=font("small", "bold"))
    style.configure("Compact.TButton", padding=(s(7), s(3)), font=font("small"))
    style.configure("CompactAccent.TButton", padding=(s(7), s(3)),
                    font=font("small", "bold"))
    style.configure("Tiny.TButton", padding=(s(6), s(2)), font=micro)

    # ---- inputs -------------------------------------------------------
    for name, border_role in (
        ("TEntry", "border"), ("Error.TEntry", "danger"),
        ("Success.TEntry", "success"),
    ):
        style.configure(
            name, fieldbackground=p["surface"], foreground=p["text"],
            insertcolor=p["text"], borderwidth=s(1), padding=(s(9), s(6)),
            bordercolor=p[border_role], lightcolor=p[border_role],
            darkcolor=p[border_role], relief="solid",
        )
        style.map(
            name,
            bordercolor=[("focus", p["focus"]), ("disabled", p["border"])],
            lightcolor=[("focus", p["focus"])],
            darkcolor=[("focus", p["focus"])],
            foreground=[("disabled", p["text_disabled"])],
            fieldbackground=[("disabled", p["surface_alt"])],
        )

    style.configure(
        "TCombobox", fieldbackground=p["surface"], foreground=p["text"],
        background=p["surface"], arrowcolor=p["text_secondary"],
        bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"],
        padding=(s(9), s(5)), arrowsize=s(14),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", p["surface"]), ("disabled", p["surface_alt"])],
        foreground=[("readonly", p["text"]), ("disabled", p["text_disabled"])],
        selectbackground=[("readonly", p["surface"])],
        selectforeground=[("readonly", p["text"])],
        bordercolor=[("focus", p["focus"])],
        arrowcolor=[("disabled", p["text_disabled"])],
    )
    root.option_add("*TCombobox*Listbox.background", p["surface"])
    root.option_add("*TCombobox*Listbox.foreground", p["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["selection"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["selection_text"])
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.font", body)
    root.option_add("*Toplevel.background", p["bg"])

    style.configure(
        "TCheckbutton", background=p["bg"], foreground=p["text"],
        font=body, padding=(0, s(3)), indicatorcolor=p["surface"],
        indicatormargin=(0, 0, s(7), 0), focuscolor=p["focus"],
    )
    style.map(
        "TCheckbutton",
        background=[("active", p["bg"])],
        foreground=[("disabled", p["text_disabled"])],
        indicatorcolor=[("selected", p["accent"]),
                        ("disabled", p["surface_alt"])],
    )
    style.configure(
        "Surface.TCheckbutton", background=p["surface"], foreground=p["text"],
        font=body, padding=(0, s(3)), indicatorcolor=p["surface"],
        indicatormargin=(0, 0, s(7), 0), focuscolor=p["focus"],
    )
    style.map(
        "Surface.TCheckbutton",
        background=[("active", p["surface"])],
        foreground=[("disabled", p["text_disabled"])],
        indicatorcolor=[("selected", p["accent"]),
                        ("disabled", p["surface_alt"])],
    )
    for name, bg_role in (("TRadiobutton", "surface"),
                          ("Surface.TRadiobutton", "bg")):
        style.configure(
            name, background=p[bg_role], foreground=p["text"], font=body,
            padding=(0, s(3)), indicatorcolor=p["surface"],
            indicatormargin=(0, 0, s(7), 0), focuscolor=p["focus"],
        )
        style.map(
            name,
            background=[("active", p[bg_role])],
            foreground=[("disabled", p["text_disabled"])],
            indicatorcolor=[("selected", p["accent"]),
                            ("disabled", p["surface_alt"])],
        )

    style.configure("TSpinbox", arrowsize=s(13), padding=(s(8), s(5)),
                    fieldbackground=p["surface"], background=p["surface"],
                    foreground=p["text"], arrowcolor=p["text_secondary"],
                    bordercolor=p["border"], lightcolor=p["border"],
                    darkcolor=p["border"])
    style.map("TSpinbox", bordercolor=[("focus", p["focus"])],
              arrowcolor=[("disabled", p["text_disabled"])],
              foreground=[("disabled", p["text_disabled"])])

    style.configure("TSeparator", background=p["border"])
    style.configure("Card.TFrame", background=p["surface"],
                    relief="solid", borderwidth=s(1), bordercolor=p["border"])

    # ---- progress -----------------------------------------------------
    style.configure(
        "TProgressbar", background=p["accent"], troughcolor=p["surface_alt"],
        bordercolor=p["surface_alt"], lightcolor=p["accent"],
        darkcolor=p["accent"], borderwidth=0, thickness=s(7),
    )
    style.configure("Success.Horizontal.TProgressbar",
                    background=p["success"], troughcolor=p["surface_alt"],
                    lightcolor=p["success"], darkcolor=p["success"],
                    borderwidth=0, thickness=s(7))

    # ---- tables -------------------------------------------------------
    style.configure(
        "Treeview", background=p["surface"], fieldbackground=p["surface"],
        foreground=p["text"], font=body, rowheight=s(tokens.ROW_HEIGHT),
        borderwidth=0, relief="flat",
    )
    style.configure(
        "Treeview.Heading", background=p["surface_alt"],
        foreground=p["text_secondary"], font=font("small", "bold"),
        relief="flat", padding=(s(8), s(7)), borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", p["selection"])],
        foreground=[("selected", p["selection_text"])],
    )
    style.map("Treeview.Heading", background=[("active", p["surface_sunken"])])

    # ---- scrollbars ---------------------------------------------------
    for orient in ("Vertical", "Horizontal"):
        style.configure(
            f"{orient}.TScrollbar", background=p["border"],
            troughcolor=p["surface"], bordercolor=p["surface"],
            arrowcolor=p["text_secondary"], gripcount=0,
            arrowsize=s(12), width=s(12),
        )
        style.map(f"{orient}.TScrollbar",
                  background=[("active", p["border_strong"])])

    # ---- notebook / misc ---------------------------------------------
    style.configure("TLabelframe", background=p["bg"], foreground=p["text_secondary"],
                    font=font("small", "bold"), borderwidth=s(1), relief="solid")
    style.configure("TLabelframe.Label", background=p["bg"],
                    foreground=p["text_secondary"], font=font("small", "bold"))

    # ---- badges / chips ----------------------------------------------
    badge_specs = {
        "BadgeNeutral.TLabel": ("surface_alt", "text_secondary"),
        "BadgeAccent.TLabel": ("selection", "text"),
        "BadgeSuccess.TLabel": ("success_bg", "success"),
        "BadgeWarning.TLabel": ("warning_bg", "warning"),
        "BadgeDanger.TLabel": ("danger_bg", "danger"),
        "BadgeInfo.TLabel": ("info_bg", "info"),
        "BadgeMuted.TLabel": ("bg", "text_secondary"),
    }
    for name, (bg_role, fg_role) in badge_specs.items():
        style.configure(name, background=p[bg_role], foreground=p[fg_role],
                        font=font("micro", "bold"), padding=(s(7), s(2)))

    # ---- inline banners ----------------------------------------------
    banner_specs = {
        "Info": ("info_bg", "info"),
        "Success": ("success_bg", "success"),
        "Warning": ("warning_bg", "warning"),
        "Danger": ("danger_bg", "danger"),
        "Neutral": ("surface_alt", "text_secondary"),
    }
    for kind, (bg_role, fg_role) in banner_specs.items():
        style.configure(f"Banner{kind}.TFrame", background=p[bg_role],
                        borderwidth=0)
        style.configure(f"Banner{kind}.TLabel", background=p[bg_role],
                        foreground=p[fg_role], font=body)
        style.configure(f"Banner{kind}Strong.TLabel", background=p[bg_role],
                        foreground=p[fg_role], font=font("small", "bold"))
        style.configure(f"Banner{kind}Body.TLabel", background=p[bg_role],
                        foreground=p["text"], font=small)

    # ---- segmented control (toolbutton radios) ----------------------
    for name, bg in (("Segment.Toolbutton", p["surface"]),
                     ("SegmentOn.Toolbutton", p["selection"])):
        style.configure(name, background=bg, foreground=p["text"],
                        font=font("small"), padding=(s(12), s(5)),
                        borderwidth=s(1), relief="flat",
                        bordercolor=p["border"], focuscolor=p["focus"])
        style.map(
            name,
            background=[("selected", p["selection"]), ("active", p["surface_alt"]),
                        ("disabled", p["surface_alt"])],
            foreground=[("selected", p["text"]), ("disabled", p["text_disabled"])],
            bordercolor=[("focus", p["focus"])],
        )

    # ---- dividers / focus borders ------------------------------------
    style.configure("Divider.TFrame", background=p["border"])
    style.configure("FocusBorder.TFrame", background=p["border"],
                    borderwidth=s(1), relief="solid")
    style.configure("FocusBorderOn.TFrame", background=p["focus"],
                    borderwidth=s(1), relief="solid")

    # ---- cards --------------------------------------------------------
    style.configure("CardInner.TFrame", background=p["surface"])
    style.configure("Toolbar.TFrame", background=p["bg"])

    # ---- sidebar navigation ------------------------------------------
    for name, bg_role in (
        ("Nav.TFrame", "sidebar"),
        ("NavHover.TFrame", "surface_alt"),
        ("NavActive.TFrame", "selection"),
        ("NavBar.TFrame", "sidebar"),
        ("NavBarActive.TFrame", "accent"),
        ("Sidebar.TFrame", "sidebar"),
        ("SidebarRule.TFrame", "border"),
    ):
        style.configure(name, background=p[bg_role])
    for name, bg_role, fg_role, fnt in (
        ("Nav.TLabel", "sidebar", "text_secondary", body),
        ("NavHover.TLabel", "surface_alt", "text", body),
        ("NavActive.TLabel", "selection", "text", body),
        ("BrandTitle.TLabel", "sidebar", "text", h1),
        ("BrandMeta.TLabel", "sidebar", "text_secondary", small),
    ):
        style.configure(name, background=p[bg_role], foreground=p[fg_role],
                        font=fnt)

    # ---- status bar ---------------------------------------------------
    style.configure("Status.TFrame", background=p["surface"])
    style.configure("Status.TLabel", background=p["surface"],
                    foreground=p["text_secondary"], font=small)
    style.configure("StatusStrong.TLabel", background=p["surface"],
                    foreground=p["text"], font=font("small", "bold"))
    style.configure("StatusRule.TFrame", background=p["border"])

    # ---- compatibility aliases used by older call sites --------------
    button("Accent.TButton", p["accent"], p["on_accent"], p["accent_hover"],
           p["accent_pressed"], bold=True, border=p["accent"])
    style.configure("SmallAccent.TButton", padding=(s(10), s(4)),
                    font=font("small", "bold"))
    style.map("SmallAccent.TButton",
              background=[("disabled", p["surface_alt"]),
                          ("pressed", p["accent_pressed"]),
                          ("active", p["accent_hover"])],
              foreground=[("disabled", p["text_disabled"])])


def configure_tree_tags(tree: ttk.Treeview, palette: dict | None = None) -> None:
    """Apply striped rows plus semantic status colours to a table."""
    p = palette or active_palette()
    tree.tag_configure("odd", background=p["row_alt"])
    tree.tag_configure("hover", background=p["surface_alt"])
    tree.tag_configure("failed", foreground=p["danger"])
    tree.tag_configure("moved", foreground=p["success"])
    tree.tag_configure("rename", foreground=p["warning"])
    tree.tag_configure("skipped", foreground=p["text_secondary"])
    tree.tag_configure("pending", foreground=p["text"])
    tree.tag_configure("section", foreground=p["text_secondary"],
                       font=font("small", "bold"))


def row_tag(index: int) -> tuple[str, ...]:
    """Tags for the *index*-th data row (striped background on odd rows)."""
    return ("odd",) if index % 2 else ()


def short_path(path: str, max_length: int = 64) -> str:
    """Shorten a path keeping both the root and the filename visible."""
    text = str(path)
    if len(text) <= max_length:
        return text
    head = max(1, (max_length - 3) // 3)
    tail = max_length - head - 3
    return text[:head] + "..." + text[-tail:]


def middle_ellipsis(text: str, max_chars: int) -> str:
    """Middle-ellipsis for filenames/paths, preserving both ends."""
    text = str(text)
    if max_chars <= 3 or len(text) <= max_chars:
        return text
    left = (max_chars - 3) // 2
    right = max_chars - 3 - left
    return text[:left] + "..." + text[-right:]
