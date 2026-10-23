"""Configuration management for EzSort."""

from __future__ import annotations

import copy
import json
import os
import platform
from pathlib import Path
from typing import Any

from ezsort.constants import DEFAULT_CATEGORIES, DEFAULT_EXCLUDED_DIRS
from ezsort.utils import atomic_write_json, backup_corrupt_file


def get_config_dir() -> Path:
    """Return the platform-appropriate configuration directory.

    Resolution order:
      1. ``EZSORT_HOME`` environment variable (portable installs, tests)
      2. ``%APPDATA%\\ezsort`` on Windows, ``~/Library/Application Support/ezsort``
         on macOS, ``~/.config/ezsort`` elsewhere.
    """
    override = os.environ.get("EZSORT_HOME")
    if override:
        return Path(override).expanduser()
    home = Path.home()
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (home / ".config"))
    return base / "ezsort"


def get_config_path() -> Path:
    """Return the path to the configuration file."""
    return get_config_dir() / "config.json"


def get_history_path() -> Path:
    """Return the path to the history file."""
    return get_config_dir() / "history.json"


def get_activity_path() -> Path:
    """Return the path to the persisted activity log."""
    return get_config_dir() / "activity.json"


def get_default_config() -> dict[str, Any]:
    """Return the default configuration dictionary."""
    return {
        "categories": copy.deepcopy(DEFAULT_CATEGORIES),
        "excluded_dirs": list(DEFAULT_EXCLUDED_DIRS),
        "excluded_extensions": [],
        "duplicate_strategy": "rename",
        "confirm_before_move": True,
        "watch_interval": 2,
        "custom_rules": [],
        "recursive": False,
        "skip_hidden": True,
        "skip_partial_downloads": True,
        "theme": "dark",
        "default_folder": "",
        "last_folder": "",
        "remember_last_folder": True,
        "window_geometry": "",
        "last_page": "dashboard",
    }


def _merge_defaults(loaded: dict[str, Any]) -> dict[str, Any]:
    """Merge a loaded config over the defaults.

    Missing keys are filled in from defaults (so configs written by older
    versions keep working) while user-provided values always win.
    """
    config = get_default_config()
    for key, value in loaded.items():
        if key in config and isinstance(config[key], dict) and isinstance(value, dict):
            merged = copy.deepcopy(config[key])
            merged.update(value)
            config[key] = merged
        else:
            config[key] = value
    return config


def _validate(config: dict[str, Any]) -> dict[str, Any]:
    """Coerce obviously-wrong values so downstream code cannot crash."""
    if not isinstance(config.get("categories"), dict):
        config["categories"] = copy.deepcopy(DEFAULT_CATEGORIES)
    clean_cats: dict[str, list[str]] = {}
    for cat, exts in config["categories"].items():
        if not isinstance(cat, str) or not isinstance(exts, (list, tuple)):
            continue
        clean_cats[cat] = [str(e).lower() for e in exts]
    config["categories"] = clean_cats or copy.deepcopy(DEFAULT_CATEGORIES)

    if not isinstance(config.get("excluded_dirs"), list):
        config["excluded_dirs"] = list(DEFAULT_EXCLUDED_DIRS)
    if not isinstance(config.get("excluded_extensions"), list):
        config["excluded_extensions"] = []
    if not isinstance(config.get("custom_rules"), list):
        config["custom_rules"] = []
    else:
        config["custom_rules"] = [
            r for r in config["custom_rules"] if isinstance(r, dict)
        ]
    config["confirm_before_move"] = bool(config.get("confirm_before_move", True))
    config["recursive"] = bool(config.get("recursive", False))
    config["skip_hidden"] = bool(config.get("skip_hidden", True))
    config["skip_partial_downloads"] = bool(
        config.get("skip_partial_downloads", True)
    )
    config["remember_last_folder"] = bool(config.get("remember_last_folder", True))
    try:
        config["watch_interval"] = max(1, int(config.get("watch_interval", 2)))
    except (TypeError, ValueError):
        config["watch_interval"] = 2
    if config.get("duplicate_strategy") not in ("rename", "skip"):
        config["duplicate_strategy"] = "rename"
    if not isinstance(config.get("theme"), str):
        config["theme"] = "dark"
    if not isinstance(config.get("default_folder"), str):
        config["default_folder"] = ""
    if not isinstance(config.get("last_folder"), str):
        config["last_folder"] = ""
    return config


def load_config() -> dict[str, Any]:
    """Load configuration from disk, returning defaults if missing/corrupt.

    A corrupt file is moved aside (``config.json.corrupt``) instead of being
    silently overwritten, and partially-written configs are completed with
    default values rather than crashing later.
    """
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("config root must be a JSON object")
            return _validate(_merge_defaults(loaded))
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            backup_corrupt_file(config_path)
    return get_default_config()


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to disk (atomically)."""
    config_path = get_config_path()
    atomic_write_json(config_path, config)


def get_categories(config: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Get category mappings from config or defaults."""
    if config and isinstance(config.get("categories"), dict) and config["categories"]:
        return config["categories"]
    return copy.deepcopy(DEFAULT_CATEGORIES)


def get_excluded_dirs(config: dict[str, Any] | None = None) -> list[str]:
    """Get excluded directory names from config."""
    if config and isinstance(config.get("excluded_dirs"), list):
        return config["excluded_dirs"]
    return list(DEFAULT_EXCLUDED_DIRS)


def get_excluded_extensions(config: dict[str, Any] | None = None) -> list[str]:
    """Get file extensions that must never be organized."""
    if config and isinstance(config.get("excluded_extensions"), list):
        return [str(e).lower() for e in config["excluded_extensions"]]
    return []


def add_custom_rule(
    config: dict[str, Any],
    rule_type: str,
    pattern: str,
    category: str,
    subfolder: str = "",
) -> dict[str, Any]:
    """Add a custom classification rule to config."""
    if "custom_rules" not in config or not isinstance(config["custom_rules"], list):
        config["custom_rules"] = []
    config["custom_rules"].append({
        "type": rule_type,
        "pattern": pattern,
        "category": category,
        "subfolder": subfolder,
    })
    return config


def remove_custom_rule(config: dict[str, Any], index: int) -> dict[str, Any]:
    """Remove a custom rule by index (silently ignores invalid indices)."""
    rules = config.get("custom_rules")
    if isinstance(rules, list) and 0 <= index < len(rules):
        rules.pop(index)
    return config
