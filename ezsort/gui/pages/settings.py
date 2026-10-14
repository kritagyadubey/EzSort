"""Settings: appearance, defaults, behavior, watch interval and maintenance."""

from __future__ import annotations

import platform
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from ezsort import __version__, engine
from ezsort.config import get_config_path, get_default_config, save_config
from ezsort.gui.pages import Page
from ezsort.gui.widgets import Card, ScrollableFrame, ToolTip

if TYPE_CHECKING:  # pragma: no cover
    from ezsort.gui.app import EzSortApp

REPO_URL = "https://github.com/kritagyadubey/EzSort"


class SettingsPage(Page):
    def __init__(self, app: "EzSortApp", parent):
        super().__init__(
            app, parent,
            "Settings",
            "Preferences are saved instantly and shared with the command-line tool.",
        )
        self._build()
        self.sync_from_config()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        scroll = ScrollableFrame(self.body)
        scroll.grid(row=0, column=0, sticky="nsew")
        host = scroll.body
        host.columnconfigure(0, weight=1)

        # ---------------- appearance ---------------------------------
        appearance = Card(host, title="Appearance")
        appearance.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        theme_row = ttk.Frame(appearance, style="Surface.TFrame")
        appearance.add(theme_row, pady=(4, 0))
        self.theme_var = tk.StringVar(value="dark")
        for value, label in (("dark", "Dark"), ("light", "Light")):
            ttk.Radiobutton(
                theme_row, text=label, value=value, variable=self.theme_var,
                command=self._theme_changed,
            ).pack(side="left", padx=(0, 16))
        appearance.add(
            ttk.Label(
                appearance,
                text="Dark is easier on the eyes at night; Light matches the OS look.",
                style="SurfaceMuted.TLabel",
            ),
            pady=(8, 0),
        )

        # ---------------- folders ------------------------------------
        folders = Card(host, title="Folders")
        folders.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        folders.columnconfigure(0, weight=1)

        row = ttk.Frame(folders, style="Surface.TFrame")
        folders.add(row, pady=(4, 0))
        row.columnconfigure(0, weight=1)
        ttk.Label(row, text="Start-up folder", style="Surface.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        entry_row = ttk.Frame(row, style="Surface.TFrame")
        entry_row.grid(row=1, column=0, sticky="ew")
        entry_row.columnconfigure(0, weight=1)
        self.default_folder_var = tk.StringVar()
        ttk.Entry(entry_row, textvariable=self.default_folder_var).grid(
            row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(entry_row, text="Browse…", command=self._pick_default_folder).grid(
            row=0, column=1, padx=(0, 8))
        ttk.Button(entry_row, text="Save", style="Accent.TButton",
                   command=self._save_default_folder).grid(row=0, column=2)

        checks = ttk.Frame(folders, style="Surface.TFrame")
        checks.grid(row=folders.next_row, column=0, sticky="w", pady=(12, 0))
        self.remember_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            checks, text="Remember the last opened folder between sessions",
            variable=self.remember_var, style="Surface.TCheckbutton",
            command=self._remember_changed,
        ).pack(anchor="w")

        # ---------------- behavior -----------------------------------
        behavior = Card(host, title="Sorting behavior")
        behavior.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        behavior.columnconfigure(0, weight=1)

        self.recursive_var = tk.BooleanVar()
        self.hidden_var = tk.BooleanVar()
        self.partial_var = tk.BooleanVar()
        self.confirm_var = tk.BooleanVar()

        behavior_checks = ttk.Frame(behavior, style="Surface.TFrame")
        behavior.add(behavior_checks, pady=(4, 0))
        ttk.Checkbutton(
            behavior_checks, text="Include subfolders by default",
            variable=self.recursive_var, style="Surface.TCheckbutton",
            command=lambda: self._toggle("recursive", self.recursive_var),
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            behavior_checks, text="Skip hidden files and folders",
            variable=self.hidden_var, style="Surface.TCheckbutton",
            command=lambda: self._toggle("skip_hidden", self.hidden_var),
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            behavior_checks,
            text="Skip unfinished downloads (.crdownload, .part, .tmp …)",
            variable=self.partial_var, style="Surface.TCheckbutton",
            command=lambda: self._toggle("skip_partial_downloads", self.partial_var),
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            behavior_checks, text="Ask for confirmation before moving files",
            variable=self.confirm_var, style="Surface.TCheckbutton",
            command=lambda: self._toggle("confirm_before_move", self.confirm_var),
        ).pack(anchor="w", pady=2)

        dup_row = ttk.Frame(behavior, style="Surface.TFrame")
        behavior.add(dup_row, pady=(10, 0))
        ttk.Label(dup_row, text="If the destination name already exists",
                  style="Surface.TLabel").pack(side="left")
        self.dup_var = tk.StringVar(value="rename")
        dup_box = ttk.Combobox(
            dup_row, textvariable=self.dup_var, state="readonly",
            values=["rename", "skip"], width=10,
        )
        dup_box.pack(side="left", padx=(10, 0))
        dup_box.bind("<<ComboboxSelected>>", lambda e: self._dup_changed())
        behavior.add(
            ttk.Label(
                behavior, style="SurfaceMuted.TLabel",
                text="'rename' stores the incoming file as 'name (1).ext'; "
                     "'skip' leaves it where it is.",
            ),
            pady=(6, 0),
        )

        # ---------------- watch --------------------------------------
        watch = Card(host, title="Watch mode")
        watch.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        watch_row = ttk.Frame(watch, style="Surface.TFrame")
        watch.add(watch_row, pady=(4, 0))
        ttk.Label(watch_row, text="Check for new files every",
                  style="Surface.TLabel").pack(side="left")
        self.interval_var = tk.StringVar(value="2")
        spin = ttk.Spinbox(
            watch_row, from_=1, to=120, textvariable=self.interval_var,
            width=5,
        )
        spin.pack(side="left", padx=(8, 4))
        ttk.Label(
            watch_row, text="seconds", style="Surface.TLabel"
        ).pack(side="left")
        ttk.Button(watch_row, text="Apply", command=self._save_interval).pack(
            side="left", padx=(10, 0))
        ToolTip(spin, "How often watch mode scans the folder (1-120 seconds).")

        # ---------------- data & maintenance -------------------------
        data = Card(host, title="Data & maintenance")
        data.grid(row=4, column=0, sticky="ew", pady=(0, 14))
        data.columnconfigure(0, weight=1)

        self.config_path_var = tk.StringVar()
        path_lbl = ttk.Label(
            data, textvariable=self.config_path_var, style="SurfaceMuted.TLabel",
            wraplength=760, justify="left",
        )
        data.add(path_lbl, pady=(2, 8))
        ToolTip(path_lbl, lambda: self.config_path_var.get())

        buttons = ttk.Frame(data, style="Surface.TFrame")
        data.add(buttons, pady=(4, 0))
        ttk.Button(buttons, text="Open config folder",
                   command=self.app.open_config_location).pack(side="left")
        ttk.Button(buttons, text="Reload from disk",
                   command=self._reload).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Reset to defaults",
                   command=self._reset_defaults).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Clear history", style="Danger.TButton",
                   command=self._clear_history).pack(side="left", padx=(8, 0))

        # ---------------- about ---------------------------------------
        about = Card(host, title="About")
        about.grid(row=5, column=0, sticky="ew", pady=(0, 14))
        info = (
            f"EzSort {__version__}  ·  MIT License  ·  by Kritagya Dubey\n"
            f"Python {platform.python_version()} on {platform.system()} "
            f"{platform.release()}  ·  {sys.executable}"
        )
        about.add(
            ttk.Label(about, text=info, style="Surface.TLabel", justify="left"),
            pady=(4, 8),
        )
        action_row = ttk.Frame(about, style="Surface.TFrame")
        about.add(action_row)
        ttk.Button(action_row, text="Open GitHub repository",
                   command=lambda: webbrowser.open(REPO_URL)).pack(side="left")
        ttk.Button(action_row, text="Report an issue",
                   command=lambda: webbrowser.open(REPO_URL + "/issues")
                   ).pack(side="left", padx=(8, 0))
        ttk.Button(
            action_row, text="Copy version",
            command=self._copy_version,
        ).pack(side="left", padx=(8, 0))

    # ------------------------------------------------------------------
    # Handlers - every control writes through to the config file
    # ------------------------------------------------------------------

    def sync_from_config(self) -> None:
        cfg = self.app.config
        self.theme_var.set(str(cfg.get("theme", "dark")))
        self.default_folder_var.set(str(cfg.get("default_folder", "")))
        self.remember_var.set(bool(cfg.get("remember_last_folder", True)))
        self.recursive_var.set(bool(cfg.get("recursive", False)))
        self.hidden_var.set(bool(cfg.get("skip_hidden", True)))
        self.partial_var.set(bool(cfg.get("skip_partial_downloads", True)))
        self.confirm_var.set(bool(cfg.get("confirm_before_move", True)))
        self.dup_var.set(str(cfg.get("duplicate_strategy", "rename")))
        self.interval_var.set(str(cfg.get("watch_interval", 2)))
        self.config_path_var.set(
            f"Configuration: {get_config_path()}"
        )

    def _theme_changed(self) -> None:
        name = self.theme_var.get()
        self.app.update_config(theme=name)
        self.app.apply_theme(name)
        self.app.log({"type": "info", "message": f"Theme switched to {name}."})

    def _pick_default_folder(self) -> None:
        initial = self.default_folder_var.get() or str(Path.home())
        chosen = filedialog.askdirectory(
            title="Choose the start-up folder", initialdir=initial,
            parent=self.app.root,
        )
        if chosen:
            self.default_folder_var.set(chosen)

    def _save_default_folder(self) -> None:
        raw = self.default_folder_var.get().strip()
        if raw and not Path(raw).expanduser().is_dir():
            self.app.toast(f"Not a folder: {raw}", "error")
            return
        self.app.update_config(default_folder=raw)

    def _remember_changed(self) -> None:
        self.app.update_config(remember_last_folder=bool(self.remember_var.get()))

    def _toggle(self, key: str, var: tk.BooleanVar) -> None:
        self.app.update_config(**{key: bool(var.get())})
        org = self.app.pages.get("organizer")
        if org is not None and org.preview is None:
            org.sync_options_from_config()

    def _dup_changed(self) -> None:
        self.app.update_config(duplicate_strategy=self.dup_var.get())

    def _save_interval(self) -> None:
        raw = self.interval_var.get().strip()
        try:
            value = int(raw)
        except ValueError:
            self.app.toast("Interval must be a number of seconds.", "error")
            self.interval_var.set(str(self.app.config.get("watch_interval", 2)))
            return
        if not 1 <= value <= 120:
            self.app.toast("Interval must be between 1 and 120 seconds.", "error")
            return
        self.app.update_config(watch_interval=value)

    def _reload(self) -> None:
        self.app.reload_config()
        self.sync_from_config()
        self.app.apply_theme(str(self.app.config.get("theme", "dark")))
        self.app.toast("Configuration reloaded from disk.", "success")
        self.app.log({"type": "info", "message": "Configuration reloaded."})

    def _reset_defaults(self) -> None:
        if not messagebox.askyesno(
            "Reset to defaults",
            "Restore every setting (theme, behavior, custom rules, folders) "
            "to the defaults?\n\nYour files and history are not affected.",
            parent=self.app.root,
        ):
            return
        try:
            save_config(get_default_config())
        except OSError as e:
            self.app.toast(f"Could not reset: {e}", "error")
            return
        self.app.reload_config()
        self.sync_from_config()
        self.app.apply_theme(str(self.app.config.get("theme", "dark")))
        cats = self.app.pages.get("categories")
        if cats is not None:
            cats.load_all()
        self.app.log({"type": "info", "message": "Settings reset to defaults."})
        self.app.toast("Settings reset to defaults.", "success")

    def _clear_history(self) -> None:
        if not messagebox.askyesno(
            "Clear history",
            "Delete the entire undo history? Previous sorts can no longer "
            "be undone.",
            parent=self.app.root,
        ):
            return
        engine.wipe_history()
        hist = self.app.pages.get("history")
        if hist is not None:
            hist.schedule_refresh()
        self.app.toast("History cleared.", "success")
        self.app.log({"type": "info", "message": "History cleared from Settings."})

    def _copy_version(self) -> None:
        text = f"EzSort {__version__} ({platform.python_version()})"
        try:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(text)
            self.app.toast(f"Copied: {text}", "success")
        except Exception as e:  # pragma: no cover
            self.app.toast(f"Could not copy: {e}", "error")

    # ------------------------------------------------------------------

    def on_show(self) -> None:
        self.sync_from_config()

    def refresh(self) -> None:
        self.sync_from_config()
