"""Settings: appearance, defaults, behavior, watch interval and maintenance."""

from __future__ import annotations

import platform
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

from ezsort import __version__, engine
from ezsort.config import get_config_path, get_default_config, save_config
from ezsort.gui.components import (
    Card,
    ConfirmDialog,
    Field,
    ScrollableFrame,
    SegmentedControl,
    ToolTip,
)
from ezsort.gui.pages import Page, sp

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
        self.header.secondary("Open config folder",
                              self.app.open_config_location,
                              style="Ghost.TButton")
        scroll = ScrollableFrame(self.body)
        scroll.grid(row=0, column=0, sticky="nsew")
        host = scroll.body
        host.columnconfigure(0, weight=1)

        # ---------------- appearance ---------------------------------
        appearance = Card(host, title="Appearance")
        appearance.grid(row=0, column=0, sticky="ew", pady=(0, sp("md")))
        theme_row = ttk.Frame(appearance.body, style="Surface.TFrame")
        theme_row.grid(row=0, column=0, sticky="w")
        ttk.Label(theme_row, text="Theme", style="Surface.TLabel").pack(
            side="left", padx=(0, sp("md")))
        self.theme_var = tk.StringVar(value="dark")
        self.theme_control = SegmentedControl(
            theme_row,
            options=[("dark", "Dark"), ("light", "Light")],
            variable=self.theme_var,
            command=self._theme_changed,
        )
        self.theme_control.pack(side="left")
        ttk.Label(
            appearance.body,
            text="Dark is a warm slate palette for night work; Light is a "
                 "warm paper palette for daylight. Both are designed "
                 "independently and meet WCAG AA contrast.",
            style="SurfaceMuted.TLabel", wraplength=720, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(sp("sm"), 0))

        # ---------------- folders ------------------------------------
        folders = Card(host, title="Folders")
        folders.grid(row=1, column=0, sticky="ew", pady=(0, sp("md")))
        self.default_field = Field(
            folders.body, "Start-up folder",
            hint="Opened when EzSort starts. Leave empty to start without a folder.",
        )
        self.default_field.grid(row=0, column=0, sticky="ew")
        folder_actions = ttk.Frame(folders.body, style="Surface.TFrame")
        folder_actions.grid(row=1, column=0, sticky="w", pady=(sp("sm"), 0))
        ttk.Button(folder_actions, text="Browse…", style="Secondary.TButton",
                   command=self._pick_default_folder).pack(side="left")
        ttk.Button(folder_actions, text="Save folder", style="Primary.TButton",
                   command=self._save_default_folder).pack(
            side="left", padx=(sp("sm"), 0))

        self.remember_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            folders.body, text="Remember the last opened folder between sessions",
            variable=self.remember_var, style="Surface.TCheckbutton",
            command=self._remember_changed,
        ).grid(row=2, column=0, sticky="w", pady=(sp("md"), 0))

        # ---------------- behavior -----------------------------------
        behavior = Card(host, title="Sorting behavior")
        behavior.grid(row=2, column=0, sticky="ew", pady=(0, sp("md")))
        behavior.body.columnconfigure(0, weight=1)

        self.recursive_var = tk.BooleanVar()
        self.hidden_var = tk.BooleanVar()
        self.partial_var = tk.BooleanVar()
        self.confirm_var = tk.BooleanVar()

        checks = ttk.Frame(behavior.body, style="Surface.TFrame")
        checks.grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            checks, text="Include subfolders by default",
            variable=self.recursive_var, style="Surface.TCheckbutton",
            command=lambda: self._toggle("recursive", self.recursive_var),
        ).pack(anchor="w", pady=sp("xxs"))
        ttk.Checkbutton(
            checks, text="Skip hidden files and folders",
            variable=self.hidden_var, style="Surface.TCheckbutton",
            command=lambda: self._toggle("skip_hidden", self.hidden_var),
        ).pack(anchor="w", pady=sp("xxs"))
        ttk.Checkbutton(
            checks,
            text="Skip unfinished downloads (.crdownload, .part, .tmp …)",
            variable=self.partial_var, style="Surface.TCheckbutton",
            command=lambda: self._toggle("skip_partial_downloads",
                                         self.partial_var),
        ).pack(anchor="w", pady=sp("xxs"))
        ttk.Checkbutton(
            checks, text="Ask for confirmation before moving files",
            variable=self.confirm_var, style="Surface.TCheckbutton",
            command=lambda: self._toggle("confirm_before_move",
                                         self.confirm_var),
        ).pack(anchor="w", pady=sp("xxs"))

        dup_row = ttk.Frame(behavior.body, style="Surface.TFrame")
        dup_row.grid(row=1, column=0, sticky="w", pady=(sp("md"), 0))
        ttk.Label(dup_row, text="If the destination name already exists",
                  style="Surface.TLabel").pack(side="left")
        self.dup_var = tk.StringVar(value="rename")
        dup_box = ttk.Combobox(
            dup_row, textvariable=self.dup_var, state="readonly",
            values=["rename", "skip"], width=10,
        )
        dup_box.pack(side="left", padx=(sp("sm"), 0))
        dup_box.bind("<<ComboboxSelected>>", lambda e: self._dup_changed())
        ToolTip(
            dup_box,
            "rename: store the incoming file as 'name (1).ext'. "
            "skip: leave it where it is.",
        )
        ttk.Label(
            behavior.body,
            text="'rename' keeps every file and adds a numbered suffix; "
                 "'skip' leaves the incoming file untouched.",
            style="SurfaceMuted.TLabel", wraplength=720, justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(sp("sm"), 0))

        # ---------------- watch --------------------------------------
        watch = Card(host, title="Watch mode")
        watch.grid(row=3, column=0, sticky="ew", pady=(0, sp("md")))
        watch_row = ttk.Frame(watch.body, style="Surface.TFrame")
        watch_row.grid(row=0, column=0, sticky="w")
        ttk.Label(watch_row, text="Check for new files every",
                  style="Surface.TLabel").pack(side="left")
        self.interval_var = tk.StringVar(value="2")
        self.interval_spin = ttk.Spinbox(
            watch_row, from_=1, to=120, textvariable=self.interval_var,
            width=6,
        )
        self.interval_spin.pack(side="left", padx=(sp("sm"), sp("xs")))
        ttk.Label(watch_row, text="seconds",
                  style="Surface.TLabel").pack(side="left")
        ttk.Button(watch_row, text="Apply", style="Secondary.TButton",
                   command=self._save_interval).pack(
            side="left", padx=(sp("md"), 0))
        self.interval_hint = ttk.Label(
            watch.body, text="Between 1 and 120 seconds.",
            style="SurfaceMuted.TLabel",
        )
        self.interval_hint.grid(row=1, column=0, sticky="w",
                                pady=(sp("xs"), 0))
        ttk.Label(
            watch.body,
            text="Watch mode starts from the Organizer page and only runs "
                 "while EzSort is open.",
            style="SurfaceMuted.TLabel", wraplength=720, justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(sp("sm"), 0))

        # ---------------- data & maintenance -------------------------
        data = Card(host, title="Data & maintenance")
        data.grid(row=4, column=0, sticky="ew", pady=(0, sp("md")))
        data.body.columnconfigure(0, weight=1)
        self.config_path_var = tk.StringVar()
        path_lbl = ttk.Label(
            data.body, textvariable=self.config_path_var,
            style="SurfaceMuted.TLabel", wraplength=720, justify="left",
        )
        path_lbl.grid(row=0, column=0, sticky="w")
        ToolTip(path_lbl, lambda: self.config_path_var.get())

        buttons = ttk.Frame(data.body, style="Surface.TFrame")
        buttons.grid(row=1, column=0, sticky="w", pady=(sp("md"), 0))
        ttk.Button(buttons, text="Open config folder", style="Secondary.TButton",
                   command=self.app.open_config_location).pack(side="left")
        ttk.Button(buttons, text="Reload from disk", style="Secondary.TButton",
                   command=self._reload).pack(side="left", padx=(sp("sm"), 0))
        ttk.Button(buttons, text="Reset to defaults", style="Danger.TButton",
                   command=self._reset_defaults).pack(
            side="left", padx=(sp("sm"), 0))
        ttk.Button(buttons, text="Clear history", style="Danger.TButton",
                   command=self._clear_history).pack(
            side="left", padx=(sp("sm"), 0))
        ttk.Label(
            data.body,
            text="Reset restores categories, rules and preferences. Your "
                 "files and undo history are never touched by Reset.",
            style="SurfaceMuted.TLabel", wraplength=720, justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(sp("sm"), 0))

        # ---------------- about --------------------------------------
        about = Card(host, title="About")
        about.grid(row=5, column=0, sticky="ew", pady=(0, sp("md")))
        info = (
            f"EzSort {__version__}  ·  MIT License  ·  by Kritagya Dubey\n"
            f"Python {platform.python_version()} on {platform.system()} "
            f"{platform.release()}  ·  {sys.executable}"
        )
        ttk.Label(about.body, text=info, style="Surface.TLabel",
                  justify="left", wraplength=720).grid(
            row=0, column=0, sticky="w", pady=(0, sp("sm")))
        action_row = ttk.Frame(about.body, style="Surface.TFrame")
        action_row.grid(row=1, column=0, sticky="w")
        ttk.Button(action_row, text="Open GitHub repository",
                   style="Secondary.TButton",
                   command=lambda: webbrowser.open(REPO_URL)).pack(side="left")
        ttk.Button(action_row, text="Report an issue", style="Secondary.TButton",
                   command=lambda: webbrowser.open(REPO_URL + "/issues")
                   ).pack(side="left", padx=(sp("sm"), 0))
        ttk.Button(action_row, text="Copy version", style="Secondary.TButton",
                   command=self._copy_version).pack(
            side="left", padx=(sp("sm"), 0))

    # ------------------------------------------------------------------
    # Handlers - every control writes through to the config file
    # ------------------------------------------------------------------

    def sync_from_config(self) -> None:
        cfg = self.app.config
        self.theme_var.set(str(cfg.get("theme", "dark")))
        self.default_field.var.set(str(cfg.get("default_folder", "")))
        self.default_field.clear_state(
            "Opened when EzSort starts. Leave empty to start without a folder.")
        self.remember_var.set(bool(cfg.get("remember_last_folder", True)))
        self.recursive_var.set(bool(cfg.get("recursive", False)))
        self.hidden_var.set(bool(cfg.get("skip_hidden", True)))
        self.partial_var.set(bool(cfg.get("skip_partial_downloads", True)))
        self.confirm_var.set(bool(cfg.get("confirm_before_move", True)))
        self.dup_var.set(str(cfg.get("duplicate_strategy", "rename")))
        self.interval_var.set(str(cfg.get("watch_interval", 2)))
        self.config_path_var.set(f"Configuration: {get_config_path()}")

    def _theme_changed(self) -> None:
        name = self.theme_var.get()
        if name not in ("dark", "light"):
            return
        self.app.update_config(theme=name, quiet=True)
        self.app.apply_theme(name)
        self.app.log({"type": "info", "message": f"Theme switched to {name}."})
        self.app.toast(f"{name.capitalize()} theme applied.", "success")

    def _pick_default_folder(self) -> None:
        initial = self.default_field.var.get() or str(Path.home())
        chosen = filedialog.askdirectory(
            title="Choose the start-up folder", initialdir=initial,
            parent=self.app.root,
        )
        if chosen:
            self.default_field.var.set(chosen)
            self.default_field.clear_state(
                "Press Save folder to keep this choice.")

    def _save_default_folder(self) -> None:
        raw = self.default_field.var.get().strip()
        if raw and not Path(raw).expanduser().is_dir():
            self.default_field.set_error(f"Not a folder: {raw}")
            return
        self.default_field.set_ok("Saved.")
        self.app.update_config(default_folder=raw, quiet=True)
        self.app.toast("Start-up folder saved.", "success")

    def _remember_changed(self) -> None:
        self.app.update_config(
            remember_last_folder=bool(self.remember_var.get()), quiet=True)
        self.app.toast("Preference saved.", "success")

    def _toggle(self, key: str, var: tk.BooleanVar) -> None:
        self.app.update_config(**{key: bool(var.get())}, quiet=True)
        self.app.toast("Preference saved.", "success")
        org = self.app.pages.get("organizer")
        if org is not None and org.preview is None:
            org.sync_options_from_config()

    def _dup_changed(self) -> None:
        self.app.update_config(duplicate_strategy=self.dup_var.get(), quiet=True)
        self.app.toast("Duplicate strategy saved.", "success")

    def _save_interval(self) -> None:
        raw = self.interval_var.get().strip()
        try:
            value = int(raw)
        except ValueError:
            self.interval_hint.configure(
                text="Enter a whole number of seconds.", foreground="#b4232d")
            return
        if not 1 <= value <= 120:
            self.interval_hint.configure(
                text="Interval must be between 1 and 120 seconds.",
                foreground="#b4232d")
            return
        self.interval_hint.configure(
            text="Saved. Watch mode uses this interval.",
            foreground=self.app.palette["success"])
        self.app.update_config(watch_interval=value, quiet=True)
        self.app.toast("Watch interval saved.", "success")

    def _reload(self) -> None:
        self.app.reload_config()
        self.sync_from_config()
        self.app.apply_theme(str(self.app.config.get("theme", "dark")))
        self.app.toast("Configuration reloaded from disk.", "success")
        self.app.log({"type": "info", "message": "Configuration reloaded."})

    def _reset_defaults(self) -> None:
        dialog = ConfirmDialog(
            self.app, "Reset everything to defaults?",
            "Categories, custom rules, folders and preferences return to "
            "their defaults.",
            details="Your files and undo history are not affected.",
            confirm_label="Reset settings", danger=True,
        )
        if not dialog.show():
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
        org = self.app.pages.get("organizer")
        if org is not None:
            org.sync_options_from_config()
            org.preview = None
        self.app.log({"type": "info", "message": "Settings reset to defaults."})
        self.app.toast("Settings reset to defaults.", "success")

    def _clear_history(self) -> None:
        dialog = ConfirmDialog(
            self.app, "Clear the undo history?",
            "Every previous sort can no longer be undone. Files are not "
            "touched.",
            confirm_label="Clear history", danger=True,
        )
        if not dialog.show():
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
