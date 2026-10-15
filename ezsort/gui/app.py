"""Main window: sidebar navigation, page hosting, shared state and status."""

from __future__ import annotations

import logging
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable, Optional

from ezsort import __version__
from ezsort.config import get_config_dir, get_config_path, load_config, save_config
from ezsort.gui import icons
from ezsort.gui.theme import apply_styles, get_palette, short_path
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


class EzSortApp:
    """The EzSort desktop application."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"EzSort {__version__}")
        self.root.minsize(980, 640)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._set_window_icon()

        self._enable_dpi_awareness()

        # --- state -------------------------------------------------------
        self.config: dict[str, Any] = load_config()
        self.palette = get_palette(self.config.get("theme", "dark"))
        self.folder: Optional[Path] = None
        last = self.config.get("last_folder") or self.config.get("default_folder")
        if last and Path(last).expanduser().is_dir():
            self.folder = Path(last).expanduser()

        self.activity: list[dict] = []
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

        # --- chrome ------------------------------------------------------
        apply_styles(self.root, self.palette)
        self._build_layout()
        self._bind_shortcuts()
        self._restore_geometry()
        self.show_page("dashboard")

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
        """Keyboard navigation: Ctrl+1..6 jump to pages, F5 refreshes."""
        for index, (key, _label) in enumerate(NAV_ITEMS, start=1):
            self.root.bind_all(
                f"<Control-Key-{index}>",
                lambda _e, k=key: self.show_page(k),
            )
        self.root.bind_all("<F5>", self._refresh_current_page)

    def _refresh_current_page(self, _event=None) -> None:
        page = self.pages.get(self.current_page)
        if page is None:
            return
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                logger.exception("page refresh failed")

    def _build_layout(self) -> None:
        p = self.palette
        self.root.configure(bg=p["bg"])
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = tk.Frame(self.root, bg=p["sidebar"], width=224, padx=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        brand = tk.Frame(self.sidebar, bg=p["sidebar"])
        brand.pack(fill="x", padx=18, pady=(22, 4))
        brand_title = tk.Label(
            brand, text="EzSort", bg=p["sidebar"], fg=p["text"],
            font=("Segoe UI", 19, "bold"), anchor="w",
        )
        brand_title.pack(side="left")
        brand_version = tk.Label(
            brand, text=f"v{__version__}", bg=p["sidebar"], fg=p["muted"],
            font=("Segoe UI", 9),
        )
        brand_version.pack(side="right", pady=(8, 0))
        brand_tagline = tk.Label(
            self.sidebar, text="Keep your files sorted,\neffortlessly.",
            bg=p["sidebar"], fg=p["muted"], font=("Segoe UI", 9),
            justify="left", anchor="w",
        )
        brand_tagline.pack(fill="x", padx=18, pady=(2, 18))
        # Kept so a theme switch can recolor the brand block (it is plain
        # tk widgets, not ttk, so ttk styles alone never reach it).
        self._brand_widgets = [
            (brand, "sidebar", None),
            (brand_title, "sidebar", "text"),
            (brand_version, "sidebar", "muted"),
            (brand_tagline, "sidebar", "muted"),
        ]

        sep = tk.Frame(self.sidebar, bg=p["border"], height=1)
        sep.pack(fill="x", padx=14, pady=(0, 8))
        self._sidebar_separators = [sep]

        self._nav_buttons: dict[str, dict] = {}
        for key, label in NAV_ITEMS:
            row = tk.Frame(self.sidebar, bg=p["sidebar"], cursor="hand2")
            row.pack(fill="x", padx=10, pady=2)
            icon = tk.Canvas(row, width=18, height=18, bg=p["sidebar"],
                             highlightthickness=0)
            icon.pack(side="left", padx=(10, 10), pady=9)
            text = tk.Label(row, text=label, bg=p["sidebar"], fg=p["muted"],
                            font=("Segoe UI", 10), anchor="w", cursor="hand2")
            text.pack(side="left", fill="x", pady=9)
            btn = {"frame": row, "icon": icon, "label": text, "key": key}
            self._nav_buttons[key] = btn
            for widget in (row, icon, text):
                widget.bind("<Enter>", lambda e, b=btn: self._hover_nav(b, True))
                widget.bind("<Leave>", lambda e, b=btn: self._hover_nav(b, False))
                widget.bind(
                    "<Button-1>",
                    lambda e, k=key: self.show_page(k),
                )

        # Sidebar footer: folder + engine status
        sep2 = tk.Frame(self.sidebar, bg=p["border"], height=1)
        sep2.pack(side="bottom", fill="x", padx=14, pady=8)
        self._sidebar_separators.append(sep2)
        self.sidebar_status = tk.Label(
            self.sidebar, text="Ready", bg=p["sidebar"], fg=p["muted"],
            font=("Segoe UI", 9), anchor="w", justify="left", wraplength=190,
        )
        self.sidebar_status.pack(side="bottom", fill="x", padx=18, pady=(4, 16))
        # Content area
        self.container = tk.Frame(self.root, bg=p["bg"])
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        # Status bar
        self.statusbar = tk.Frame(self.root, bg=p["surface"], height=28)
        self.statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.statusbar.grid_propagate(False)
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(
            self.statusbar, textvariable=self.status_var, bg=p["surface"],
            fg=p["muted"], font=("Segoe UI", 9), anchor="w", padx=14,
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self.task_label = tk.Label(
            self.statusbar, text="", bg=p["surface"], fg=p["muted"],
            font=("Segoe UI", 9), anchor="e", padx=14,
        )
        self.task_label.pack(side="right")

    def _hover_nav(self, btn: dict, entering: bool) -> None:
        p = self.palette
        selected = btn["key"] == self.current_page
        if selected:
            bg, fg = p["selection"], p["text"]
        else:
            bg, fg = (p["surface_alt"], p["text"]) if entering else (p["sidebar"], p["muted"])
        btn["frame"].configure(bg=bg)
        btn["label"].configure(bg=bg, fg=fg)
        btn["icon"].configure(bg=bg)
        icons.draw_icon(
            btn["icon"], btn["key"],
            p["text"] if (entering or selected) else p["muted"],
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

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
        try:
            page.on_show()
        except Exception:
            logger.exception("page on_show failed")
        self.current_page = name
        p = self.palette
        for key, btn in self._nav_buttons.items():
            selected = key == name
            bg = p["selection"] if selected else p["sidebar"]
            fg = p["text"] if selected else p["muted"]
            btn["frame"].configure(bg=bg)
            btn["label"].configure(bg=bg, fg=fg)
            btn["icon"].configure(bg=bg)
            icons.draw_icon(btn["icon"], key, p["text"] if selected else p["muted"])

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
        """Show a transient status message (info/success/warning/error)."""
        colors = {
            "info": self.palette["muted"],
            "success": self.palette["success"],
            "warning": self.palette["warning"],
            "error": self.palette["danger"],
        }
        self.status_var.set(message)
        self.status_label.configure(fg=colors.get(kind, self.palette["muted"]))
        if self._status_job:
            try:
                self.root.after_cancel(self._status_job)
            except Exception:
                pass
        if kind in ("success", "info"):
            self._status_job = self.root.after(
                6000,
                lambda: self.status_var.set(
                    f"Folder: {short_path(str(self.folder), 70)}" if self.folder
                    else "Ready"
                ),
            )

    def set_busy(self, label: str) -> None:
        self._active_label = label
        self.task_label.configure(
            text=f"{label}…",
            fg=self.palette["accent"],
        )
        self.sidebar_status.configure(text=f"Busy: {label}")
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
            # Something else is still running - keep an honest indicator.
            current = self._running_labels[-1]
            self.task_label.configure(text=f"{current}…", fg=self.palette["accent"])
            self.sidebar_status.configure(
                text=(
                    f"Watching:\n{short_path(str(self.folder), 34)}"
                    if self.watching else f"Busy: {current}"
                )
            )
            return
        self.task_label.configure(text="", fg=self.palette["muted"])
        self.sidebar_status.configure(
            text=(
                f"Watching:\n{short_path(str(self.folder), 34)}"
                if self.watching else "Ready"
            )
        )

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
        """Cancel the cancellable task (organizing). Scans/undo finish fast
        on their own; watch mode is stopped from the Organizer page."""
        token = self._cancel_tokens.get("organizing")
        if token is not None:
            token.cancel()
            self.toast("Cancelling - finishing the current file first…", "warning")
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

        page = self.pages.get("activity")
        if page is not None:
            page.append_entry(entry)
        page = self.pages.get("dashboard")
        if page is not None and entry.get("type") in ("moved", "failed", "error", "undone"):
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

    def update_config(self, **values: Any) -> None:
        """Persist configuration changes immediately."""
        self.config.update(values)
        try:
            save_config(self.config)
        except OSError as e:
            self.toast(f"Could not save settings: {e}", "error")
            return
        self.toast("Settings saved.", "success")

    def apply_theme(self, name: str) -> None:
        self.palette = get_palette(name)
        apply_styles(self.root, self.palette)
        # Rebuild chrome colours.
        p = self.palette
        self.root.configure(bg=p["bg"])
        self.sidebar.configure(bg=p["sidebar"])
        self.container.configure(bg=p["bg"])
        self.statusbar.configure(bg=p["surface"])
        self.status_label.configure(bg=p["surface"], fg=p["muted"])
        self.task_label.configure(bg=p["surface"], fg=p["muted"])
        self.sidebar_status.configure(bg=p["sidebar"], fg=p["muted"])
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
        # Force every page to re-skin itself.
        for page in self.pages.values():
            try:
                page.apply_theme()
            except Exception:
                logger.exception("theme refresh failed for %s", page)
        # Re-select nav to redraw icons.
        current, self.current_page = self.current_page, ""
        if current:
            self.show_page(current)

    def open_config_location(self) -> None:
        path = get_config_path()
        try:
            get_config_dir().mkdir(parents=True, exist_ok=True)
            if hasattr(self.root, "tk"):
                import os

                if os.name == "nt":
                    os.startfile(str(path.parent))  # noqa: S606
                else:  # pragma: no cover - non-Windows convenience
                    os.system(f'xdg-open "{path.parent}"')  # noqa: S605
        except Exception as e:
            messagebox.showinfo("Configuration", f"{path}\n\n({e})", parent=self.root)

    # ------------------------------------------------------------------
    # Geometry / lifecycle
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        geometry = self.config.get("window_geometry", "")
        if isinstance(geometry, str) and geometry:
            try:
                self.root.geometry(geometry)
            except tk.TclError:
                pass
        else:
            self.root.geometry("1180x760")

    def on_close(self) -> None:
        if self._watch_stop is not None:
            self._watch_stop.set()
        geometry = self.root.geometry()  # e.g. 1180x760+10+20
        try:
            self.config = load_config()
            self.config["window_geometry"] = geometry
            if self.folder:
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


__all__ = ["EzSortApp"]
