"""Main window: sidebar navigation, page hosting, shared state and status.

The shell owns every cross-page service (configuration, background tasks,
activity log, theming, toasts) so pages only describe their own content.
"""

from __future__ import annotations

import logging
import re
import sys
import threading
import tkinter as tk
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from ezsort import __version__
from ezsort.activity import append_activity, load_activity, save_activity
from ezsort.config import (
    get_config_dir,
    get_config_path,
    load_config,
    save_config,
)
from ezsort.gui import components, icons, theme, tokens
from ezsort.gui.components import ErrorDialog, IconCanvas, Toast
from ezsort.gui.tokens import SPACE
from ezsort.gui.workers import CancelToken, TaskRunner

logger = logging.getLogger(__name__)

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("organizer", "Organizer"),
    ("categories", "Categories & Rules"),
    ("history", "History & Undo"),
    ("activity", "Activity"),
    ("settings", "Settings"),
]

MAX_ACTIVITY = 500

_GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$")


def app_icon_path() -> Optional[Path]:
    """Locate the bundled application icon (source tree or frozen EXE).

    PyInstaller stores data files under ``sys._MEIPASS``; when running from
    source the icon lives in ``packaging/``. Returns None when the icon
    cannot be found so callers can degrade gracefully.
    """
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            # packaging/ezsort-gui.spec bundles the icon into the
            # "packaging" folder inside the bundle; the root is kept as a
            # fallback in case a spec ever places it there instead.
            candidates.append(Path(meipass) / "packaging" / "ezsort.ico")
            candidates.append(Path(meipass) / "ezsort.ico")
        candidates.append(Path(sys.executable).with_suffix(".ico"))
    else:
        candidates.append(
            Path(__file__).resolve().parents[2] / "packaging" / "ezsort.ico"
        )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:  # pragma: no cover - unreadable install dir
            continue
    return None


def _sp(key: str) -> int:
    return tokens.sc(SPACE[key])


class EzSortApp:
    """The EzSort desktop application."""

    def __init__(self) -> None:
        # DPI awareness must be requested *before* the first Tk window is
        # created, otherwise Windows bitmap-scales the whole UI.
        self._enable_dpi_awareness()
        self.root = tk.Tk()
        self._set_scale()

        self.root.title(f"EzSort {__version__}")
        self.root.minsize(tokens.sc(tokens.MIN_WINDOW[0]),
                          tokens.sc(tokens.MIN_WINDOW[1]))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.report_callback_exception = self._report_callback_exception
        self._set_window_icon()

        # --- state -------------------------------------------------------
        self.config: dict[str, Any] = load_config()
        self.palette = theme.get_palette(self.config.get("theme", "dark"))
        self.folder: Optional[Path] = None
        last = self.config.get("last_folder") or self.config.get("default_folder")
        if last and Path(last).expanduser().is_dir():
            self.folder = Path(last).expanduser()

        self.activity: list[dict] = load_activity(MAX_ACTIVITY)
        self.runner = TaskRunner(self.root)
        self._task_lock = threading.Lock()
        #: One cancel token per running task (label -> token), so a
        #: background watch can never hijack the organize cancel button.
        self._cancel_tokens: dict[str, CancelToken] = {}
        #: Labels of currently running tasks (in start order); the busy
        #: indicator reflects whatever is still alive.
        self._running_labels: list[str] = []
        self._active_label = ""
        self._status_job: Optional[str] = None
        self.watching = False
        self._watch_stop: Optional[threading.Event] = None
        self.pages: dict[str, Any] = {}
        self.current_page = ""
        self._nav_buttons: dict[str, dict] = {}

        # --- chrome ------------------------------------------------------
        theme.apply_styles(self.root, self.palette)
        self._build_layout()
        self._bind_shortcuts()
        self._restore_geometry()
        self._refresh_status()
        start = str(self.config.get("last_page") or "dashboard")
        if start not in dict(NAV_ITEMS):
            start = "dashboard"
        self.show_page(start)

    # ------------------------------------------------------------------
    # Window / chrome
    # ------------------------------------------------------------------

    @staticmethod
    def _enable_dpi_awareness() -> None:
        """Make the window crisp on high-DPI and mixed-scale displays.

        Per-monitor v2 is preferred (correct on mixed 100%/150% setups);
        older Windows 10 builds fall back to system-DPI awareness.
        """
        try:
            import ctypes

            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == -4
            if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except Exception:
            pass
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _set_scale(self) -> None:
        """Derive one UI scale from the real display DPI."""
        dpi = 96.0
        try:
            dpi = float(self.root.winfo_fpixels("1i"))
        except Exception:  # pragma: no cover - unusual Tk build
            pass
        tokens.set_scale(tokens.scale_from_dpi(dpi))

    def _set_window_icon(self) -> None:
        """Use the real EzSort icon for the window (title bar, taskbar)."""
        icon = app_icon_path()
        if icon is None:
            return
        try:
            self.root.iconbitmap(str(icon))
        except Exception:  # pragma: no cover - never block startup on an icon
            logger.debug("Could not set window icon", exc_info=True)

    def _bind_shortcuts(self) -> None:
        """Keyboard navigation: Ctrl+1..6 pages, Ctrl+F search, F5 refresh."""
        for index, (key, _label) in enumerate(NAV_ITEMS, start=1):
            self.root.bind_all(
                f"<Control-Key-{index}>",
                lambda _e, k=key: self.show_page(k),
            )
        self.root.bind_all("<F5>", self._refresh_current_page)
        self.root.bind_all("<Control-f>", self._focus_search)
        self.root.bind_all("<Control-F>", self._focus_search)
        self.root.bind_all("<Control-o>", self._choose_folder_shortcut)
        self.root.bind_all("<Control-O>", self._choose_folder_shortcut)
        self.root.bind_all("<F1>", self._show_shortcuts)
        self.root.bind_all("<Escape>", self._escape)

    def _refresh_current_page(self, _event=None) -> None:
        page = self.pages.get(self.current_page)
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                logger.exception("page refresh failed")
        return "break"

    def _focus_search(self, _event=None) -> str:
        page = self.pages.get("organizer")
        if page is None:
            self.show_page("organizer")
            page = self.pages.get("organizer")
        if self.current_page != "organizer":
            self.show_page("organizer")
        focus = getattr(page, "focus_search", None)
        if callable(focus):
            focus()
        return "break"

    def _choose_folder_shortcut(self, _event=None) -> str:
        page = self.pages.get("organizer")
        if page is None:
            self.show_page("organizer")
            page = self.pages.get("organizer")
        choose = getattr(page, "choose_folder", None)
        if callable(choose):
            choose()
        return "break"

    def _show_shortcuts(self, _event=None) -> str:
        components.ShortcutsDialog(self).show()
        return "break"

    def _escape(self, _event=None) -> None:
        page = self.pages.get(self.current_page)
        clear = getattr(page, "escape", None)
        if callable(clear):
            try:
                clear()
            except Exception:
                logger.debug("escape handler failed", exc_info=True)

    def _build_layout(self) -> None:
        p = self.palette
        self.root.configure(bg=p["bg"])
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._build_sidebar()

        self.container = ttk.Frame(self.root, style="TFrame")
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        self._build_statusbar()
        self.toast_host = Toast(self, self.container)

    def _build_sidebar(self) -> None:
        p = self.palette
        sidebar_width = _sp("xl") + tokens.sc(tokens.SIDEBAR_WIDTH)
        # A weighted content column would otherwise squeeze the sidebar below
        # its designed width on narrow screens.
        self.root.columnconfigure(0, minsize=sidebar_width)
        self.sidebar = tk.Frame(self.root, bg=p["sidebar"], width=sidebar_width)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        brand = tk.Frame(self.sidebar, bg=p["sidebar"])
        brand.pack(fill="x", padx=_sp("lg"), pady=(_sp("xl"), 0))
        brand_title = tk.Label(
            brand, text="EzSort", bg=p["sidebar"], fg=p["text"],
            font=theme.font("h1", "bold"), anchor="w",
        )
        brand_title.pack(side="left")
        brand_version = tk.Label(
            brand, text=f"v{__version__}", bg=p["sidebar"],
            fg=p["text_secondary"], font=theme.font("small"),
        )
        brand_version.pack(side="right", pady=(_sp("xs"), 0))
        brand_tagline = tk.Label(
            self.sidebar, text="Keep every download in its place.",
            bg=p["sidebar"], fg=p["text_secondary"], font=theme.font("small"),
            justify="left", anchor="w", wraplength=tokens.sc(190),
        )
        brand_tagline.pack(fill="x", padx=_sp("lg"), pady=(_sp("xxs"), _sp("lg")))
        # Kept so a theme switch can recolor the brand block (plain tk
        # widgets are not reached by ttk styles).
        self._brand_widgets = [
            (brand, "sidebar", None),
            (brand_title, "sidebar", "text"),
            (brand_version, "sidebar", "text_secondary"),
            (brand_tagline, "sidebar", "text_secondary"),
        ]

        self._sidebar_separators: list[tk.Frame] = []
        sep = tk.Frame(self.sidebar, bg=p["border"], height=1)
        sep.pack(fill="x", padx=_sp("md"), pady=(0, _sp("sm")))
        self._sidebar_separators.append(sep)

        for key, label in NAV_ITEMS:
            row = ttk.Frame(self.sidebar, style="Nav.TFrame",
                            cursor="hand2")
            row.pack(fill="x", padx=_sp("sm"), pady=_sp("xxs"))
            row.columnconfigure(2, weight=1)
            bar = ttk.Frame(row, style="NavBar.TFrame", width=_sp("xxs"))
            bar.grid(row=0, column=0, sticky="ns")
            bar.grid_propagate(False)
            icon = IconCanvas(row, key, role="text_secondary",
                              bg_role="sidebar", size=tokens.sc(icons.SIZE))
            icon.grid(row=0, column=1, padx=(_sp("md"), _sp("sm")),
                      pady=_sp("sm"))
            text = ttk.Label(row, text=label, style="Nav.TLabel", anchor="w")
            text.grid(row=0, column=2, sticky="ew", padx=(0, _sp("sm")),
                      pady=_sp("sm"))
            btn = {"frame": row, "bar": bar, "icon": icon, "label": text,
                   "key": key}
            self._nav_buttons[key] = btn
            for widget in (row, bar, icon, text):
                widget.bind("<Enter>", lambda e, b=btn: self._hover_nav(b, True))
                widget.bind("<Leave>", lambda e, b=btn: self._hover_nav(b, False))
                widget.bind("<Button-1>", lambda e, k=key: self.show_page(k))

        # Sidebar footer: folder + engine status
        sep2 = tk.Frame(self.sidebar, bg=p["border"], height=1)
        sep2.pack(side="bottom", fill="x", padx=_sp("md"), pady=_sp("sm"))
        self._sidebar_separators.append(sep2)
        self.sidebar_status_var = tk.StringVar(value="Ready")
        self.sidebar_status = ttk.Label(
            self.sidebar, textvariable=self.sidebar_status_var,
            style="SidebarMuted.TLabel", anchor="w", justify="left",
            wraplength=tokens.sc(190),
        )
        self.sidebar_status.pack(side="bottom", fill="x", padx=_sp("lg"),
                                 pady=(_sp("xs"), _sp("lg")))

    def _build_statusbar(self) -> None:
        self.statusbar = ttk.Frame(self.root, style="Status.TFrame",
                                   height=_sp("xl"))
        self.statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.statusbar.grid_propagate(False)
        rule = ttk.Frame(self.statusbar, style="StatusRule.TFrame",
                         height=tokens.sc(1))
        rule.pack(side="top", fill="x")
        inner = ttk.Frame(self.statusbar, style="Status.TFrame")
        inner.pack(fill="both", expand=True, padx=_sp("md"))
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(
            inner, textvariable=self.status_var, style="Status.TLabel",
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self.task_var = tk.StringVar(value="")
        self.task_label = ttk.Label(
            inner, textvariable=self.task_var, style="StatusStrong.TLabel",
            anchor="e",
        )
        self.task_label.pack(side="right")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _hover_nav(self, btn: dict, entering: bool) -> None:
        if btn["key"] == self.current_page:
            return
        style = "NavHover.TFrame" if entering else "Nav.TFrame"
        label_style = "NavHover.TLabel" if entering else "Nav.TLabel"
        try:
            btn["frame"].configure(style=style)
            btn["label"].configure(style=label_style)
            btn["icon"].set_roles(
                "surface_alt" if entering else "sidebar",
                "text" if entering else "text_secondary",
            )
        except tk.TclError:
            pass

    def _paint_nav(self) -> None:
        for key, btn in self._nav_buttons.items():
            selected = key == self.current_page
            try:
                btn["frame"].configure(
                    style="NavActive.TFrame" if selected else "Nav.TFrame")
                btn["label"].configure(
                    style="NavActive.TLabel" if selected else "Nav.TLabel")
                btn["bar"].configure(
                    style="NavBarActive.TFrame" if selected else "NavBar.TFrame")
                btn["icon"].set_roles(
                    "selection" if selected else "sidebar",
                    "text" if selected else "text_secondary",
                )
            except tk.TclError:  # pragma: no cover - widget destroyed
                pass

    def show_page(self, name: str) -> None:
        if name not in self.pages:
            page_cls = self._page_class(name)
            if page_cls is None:
                return
            page = page_cls(self, self.container)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page

        page = self.pages[name]
        page.lift()
        self.current_page = name
        self._paint_nav()
        try:
            page.on_show()
        except Exception:
            logger.exception("page on_show failed")
        self._refresh_status()

    @staticmethod
    def _page_class(name: str):
        from ezsort.gui.pages.activity import ActivityPage
        from ezsort.gui.pages.categories import CategoriesPage
        from ezsort.gui.pages.dashboard import DashboardPage
        from ezsort.gui.pages.history import HistoryPage
        from ezsort.gui.pages.organizer import OrganizerPage
        from ezsort.gui.pages.settings import SettingsPage

        return {
            "dashboard": DashboardPage,
            "organizer": OrganizerPage,
            "categories": CategoriesPage,
            "history": HistoryPage,
            "activity": ActivityPage,
            "settings": SettingsPage,
        }.get(name)

    # ------------------------------------------------------------------
    # Shared services for pages
    # ------------------------------------------------------------------

    def toast(self, message: str, kind: str = "info") -> None:
        """Show a transient, non-blocking status message."""
        if kind == "error":
            kind = "danger"
        if kind not in ("info", "success", "warning", "danger"):
            kind = "info"
        try:
            self.toast_host.show(message, kind)
        except Exception:  # pragma: no cover - toast host going away
            logger.debug("toast failed", exc_info=True)
        self.status_var.set(message)

    def set_folder(self, folder: Optional[Path]) -> None:
        """Adopt *folder* app-wide and refresh every place that shows it."""
        self.folder = folder
        self._refresh_status()
        if self.current_page:
            page = self.pages.get(self.current_page)
            if page is not None:
                sync = getattr(page, "sync_folder", None)
                if callable(sync):
                    try:
                        sync()
                    except Exception:
                        logger.debug("folder sync failed", exc_info=True)

    def _refresh_status(self) -> None:
        if self.folder:
            text = f"Folder: {theme.short_path(str(self.folder), 78)}"
        else:
            text = "No folder selected - choose one in the Organizer."
        if not self._running_labels:
            self.status_var.set(text)
        if self.watching and self.folder:
            self.sidebar_status_var.set(
                "Watching\n" + theme.short_path(str(self.folder), 30))
            self.task_var.set("Watching for new files")
        elif self._running_labels:
            label = self._running_labels[-1]
            self.sidebar_status_var.set(f"Busy: {label}")
            self.task_var.set(f"{label.capitalize()}…")
        else:
            self.sidebar_status_var.set(
                theme.short_path(str(self.folder), 30) if self.folder
                else "No folder selected"
            )
            self.task_var.set("")

    def set_busy(self, label: str) -> None:
        self._active_label = label
        self.task_var.set(f"{label.capitalize()}…")
        self.sidebar_status_var.set(f"Busy: {label}")
        if label == "watching":
            self.watching = True

    def end_busy(self, label: str = "") -> None:
        """Clear the busy indicator once no task needs it anymore.

        Other tasks (e.g. watch mode) may still be running, so the
        indicator switches to whatever remains instead of lying about
        the app being idle.
        """
        if self.watching and label == "watching":
            self.watching = False
        if self._running_labels:
            self._refresh_status()
            return
        self.task_var.set("")
        self._refresh_status()

    def _discard_label(self, label: str) -> None:
        """Forget one running-task entry (labels may repeat)."""
        try:
            self._running_labels.remove(label)
        except ValueError:
            pass

    def start_task(
        self,
        label: str,
        fn: Callable[[], Any],
        on_done: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[BaseException], None]] = None,
        exclusive: bool = True,
    ) -> bool:
        """Run a background task with busy indication.

        Returns False when an exclusive task is already running.
        """
        if exclusive and not self._task_lock.acquire(blocking=False):
            self.toast(
                "Another operation is already running - wait for it to finish.",
                "warning",
            )
            return False

        token = CancelToken()
        self._cancel_tokens[label] = token
        self._running_labels.append(label)
        self.set_busy(label)

        def wrapped():
            try:
                return fn()
            finally:
                if exclusive:
                    self._task_lock.release()

        def done(result):
            try:
                if on_done:
                    on_done(result)
            finally:
                self._discard_label(label)
                self.end_busy(label)
                if self._cancel_tokens.get(label) is token:
                    self._cancel_tokens.pop(label, None)

        def failed(exc):
            try:
                if on_error:
                    on_error(exc)
                else:
                    self.toast(f"{label} failed: {exc}", "error")
                    logger.exception("%s failed", label)
            finally:
                self._discard_label(label)
                self.end_busy(label)
                if self._cancel_tokens.get(label) is token:
                    self._cancel_tokens.pop(label, None)

        self.runner.submit(wrapped, on_done=done, on_error=failed)
        return True

    def cancel_token_for(self, label: str) -> Optional[CancelToken]:
        """Cancel token of a specific running task (None when absent)."""
        return self._cancel_tokens.get(label)

    def cancel_current(self) -> None:
        """Cancel the cancellable task (organizing)."""
        token = self._cancel_tokens.get("organizing")
        if token is not None:
            token.cancel()
            self.toast("Cancelling - finishing the current file first…",
                       "warning")
        else:
            self.toast("Nothing cancellable is running.", "info")

    def is_busy(self) -> bool:
        """True while an exclusive (file-mutating) task is running."""
        return self._task_lock.locked()

    # -- activity log ----------------------------------------------------

    def log(self, payload: dict) -> None:
        entry = dict(payload)
        entry.setdefault("time", datetime.now().strftime("%H:%M:%S"))
        entry.setdefault("type", "info")
        self.activity.append(entry)
        if len(self.activity) > MAX_ACTIVITY:
            self.activity = self.activity[-MAX_ACTIVITY:]
            save_activity(self.activity)
        else:
            append_activity(entry, MAX_ACTIVITY)

        page = self.pages.get("activity")
        if page is not None:
            page.append_entry(entry)
        page = self.pages.get("dashboard")
        if page is not None and entry.get("type") in (
                "moved", "failed", "error", "undone", "cancelled"):
            page.refresh_recent()

        kind = entry.get("type")
        message = entry.get("message", "")
        if kind in ("error", "failed"):
            self.toast(message, "error")
        elif kind == "moved":
            self.toast(message, "success")

    # -- config ----------------------------------------------------------

    def reload_config(self) -> None:
        self.config = load_config()

    def update_config(self, quiet: bool = False, **values: Any) -> None:
        """Persist configuration changes immediately."""
        self.config.update(values)
        try:
            save_config(self.config)
        except OSError as e:
            self.toast(f"Could not save settings: {e}", "error")
            return
        if not quiet:
            self.toast("Saved.", "success")

    def apply_theme(self, name: str) -> None:
        self.palette = theme.get_palette(name)
        theme.apply_styles(self.root, self.palette)
        p = self.palette
        self.root.configure(bg=p["bg"])
        self.sidebar.configure(bg=p["sidebar"])
        self.container.configure(style="TFrame")
        # The brand block and separators are plain tk widgets (ttk styles
        # never reach them), so recolor them explicitly.
        for widget, bg_role, fg_role in self._brand_widgets:
            try:
                widget.configure(bg=p[bg_role])
                if fg_role:
                    widget.configure(fg=p[fg_role])
            except tk.TclError:  # pragma: no cover - widget destroyed
                pass
        for sep_widget in self._sidebar_separators:
            try:
                sep_widget.configure(bg=p["border"])
            except tk.TclError:  # pragma: no cover - widget destroyed
                pass
        for page in self.pages.values():
            try:
                page.apply_theme()
            except Exception:
                logger.exception("theme refresh failed for %s", page)
        self._theme_walk(self.root, p)
        self._paint_nav()

    def _theme_walk(self, widget, palette: dict) -> None:
        """Re-skin raw-canvas components and dialogs after a theme switch."""
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            if getattr(child, "THEME_AWARE", False):
                try:
                    child.apply_theme(palette)
                except Exception:
                    logger.debug("theme-aware widget failed", exc_info=True)
            self._theme_walk(child, palette)

    def open_config_location(self) -> None:
        path = get_config_path()
        try:
            get_config_dir().mkdir(parents=True, exist_ok=True)
            import os

            if os.name == "nt":
                os.startfile(str(path.parent))  # noqa: S606
                self.toast("Opened the configuration folder.", "info")
            else:  # pragma: no cover - non-Windows convenience
                import subprocess

                subprocess.Popen(["xdg-open", str(path.parent)])  # noqa: S603,S607
                self.toast("Opened the configuration folder.", "info")
        except Exception as e:
            self.toast(f"Could not open {path.parent}: {e}", "error")

    # ------------------------------------------------------------------
    # Errors / lifecycle
    # ------------------------------------------------------------------

    def _report_callback_exception(self, exc, value, tb) -> None:
        """Show a friendly dialog instead of silently swallowing errors."""
        logger.error("Unhandled UI error", exc_info=(exc, value, tb))
        details = "".join(traceback.format_exception(exc, value, tb))
        summary = (
            "EzSort hit an unexpected error while handling that action. "
            "Your files were not touched beyond what the page reports."
        )
        try:
            ErrorDialog(self, summary, details).show()
        except Exception:  # pragma: no cover - dialog itself failed
            try:
                messagebox.showerror("EzSort", f"{summary}\n\n{value}",
                                     parent=self.root)
            except Exception:
                pass

    @staticmethod
    def _work_area() -> tuple[int, int]:
        """Return the usable desktop size (excludes the Windows taskbar)."""
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            # SPI_GETWORKAREA == 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(
                    0x0030, 0, ctypes.byref(rect), 0):
                return rect.right - rect.left, rect.bottom - rect.top
        except Exception:
            pass
        return 0, 0

    def _restore_geometry(self) -> None:
        geometry = self.config.get("window_geometry", "")
        width, height = (tokens.sc(v) for v in tokens.DEFAULT_WINDOW)
        x = y = None
        match = _GEOMETRY_RE.match(geometry) if isinstance(geometry, str) else None
        if match:
            width = max(tokens.sc(tokens.MIN_WINDOW[0]), int(match.group(1)))
            height = max(tokens.sc(tokens.MIN_WINDOW[1]), int(match.group(2)))
            x, y = int(match.group(3)), int(match.group(4))
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        work_w, work_h = self._work_area()
        work_w = work_w or screen_w
        work_h = work_h or screen_h
        # Leave room for the title bar and a visible desktop margin; using the
        # work area keeps the status bar above the taskbar.
        width = min(width, max(tokens.sc(tokens.MIN_WINDOW[0]), work_w - 40))
        height = min(height, max(tokens.sc(tokens.MIN_WINDOW[1]), work_h - 120))
        if x is None or y is None:
            x = max(0, (work_w - width) // 2)
            y = max(0, (work_h - height) // 2 - 20)
        x = max(0, min(x, work_w - width - 8))
        y = max(0, min(y, work_h - height - 48))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def on_close(self) -> None:
        if self._watch_stop is not None:
            self._watch_stop.set()
        geometry = self.root.geometry()
        try:
            self.config = load_config()
            self.config["window_geometry"] = geometry
            self.config["last_page"] = self.current_page or "dashboard"
            if self.folder and self.config.get("remember_last_folder", True):
                self.config["last_folder"] = str(self.folder)
            save_config(self.config)
        except Exception:
            logger.warning("Could not persist window state", exc_info=True)
        self.runner.close()
        self.root.destroy()

    def main_loop(self) -> int:
        try:
            self.root.mainloop()
        except KeyboardInterrupt:  # pragma: no cover
            pass
        return 0


__all__ = ["EzSortApp", "app_icon_path", "NAV_ITEMS"]
