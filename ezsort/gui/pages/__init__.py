"""Base class shared by all application pages."""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from ezsort.gui.widgets import PageHeader

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp

logger = logging.getLogger(__name__)


class Page(ttk.Frame):
    """A navigation page with a header row and a body row.

    ``self.body`` is the widget pages fill; ``self.header`` provides the
    title/subtitle and a slot for page-level actions.
    """

    #: Palette role mapping used by :meth:`register` for live re-theming.
    ROLES = {
        "bg": "bg",
        "surface": "surface",
        "surface_alt": "surface_alt",
        "text": "text",
        "muted": "muted",
        "border": "border",
        "selection": "selection",
        "sidebar": "sidebar",
    }

    def __init__(self, app: "EzSortApp", parent, title: str, subtitle: str = ""):
        super().__init__(parent, style="TFrame")
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.header = PageHeader(self, title, subtitle)
        self.header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 16))

        self.body = ttk.Frame(self, style="TFrame")
        self.body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 22))
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)

        self._themed: list[tuple[Any, str]] = []

    # -- theming ---------------------------------------------------------

    def register(self, widget, role: str):
        """Remember a raw Tk widget so theme switches can recolor it."""
        self._themed.append((widget, role))
        return widget

    def apply_theme(self) -> None:
        """Re-color raw Tk widgets; ttk widgets restyle automatically."""
        palette = self.app.palette
        keep: list[tuple[Any, str]] = []
        for widget, role in self._themed:
            try:
                if not widget.winfo_exists():
                    continue
            except Exception:
                continue
            keep.append((widget, role))
            try:
                widget.configure(bg=palette.get(role, palette["bg"]))
            except Exception:
                logger.debug("Failed to re-theme widget", exc_info=True)
        self._themed = keep

    def recolor_label(self, label, fg_role: str = "text", bg_role: str = "surface") -> None:
        palette = self.app.palette
        try:
            label.configure(fg=palette[fg_role], bg=palette[bg_role])
        except Exception:
            pass

    # -- lifecycle -------------------------------------------------------

    def on_show(self) -> None:
        """Called each time the page becomes visible (override as needed)."""

    def refresh(self) -> None:
        """Reload data from disk (override as needed)."""
