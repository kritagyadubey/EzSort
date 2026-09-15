"""Configuration management for EzSort."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from ezsort.constants import DEFAULT_CATEGORIES, DEFAULT_EXCLUDED_DIRS


def get_config_dir() -> Path:
    """Return the platform-appropriate configuration directory."""
    if platform.system() == "Windows":
        base = Path.home() / "AppData" / "Roaming"
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "ezsort"


def get_config_path() -> Path:
    """Return the path to the configuration file."""
    return get_config_dir() / "config.json"


def get_history_path() -> Path:
    """Return the path to the history file."""
    return get_config_dir() / "history.json"


def load_config() -> dict[str, Any]:
    """Load configuration from disk, returning defaults if missing."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return get_default_config()


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to disk."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_default_config() -> dict[str, Any]:
    """Return the default configuration dictionary."""
    return {
        "categories": DEFAULT_CATEGORIES,
        "excluded_dirs": DEFAULT_EXCLUDED_DIRS,
        "excluded_extensions": [],
        "duplicate_strategy": "rename",
        "confirm_before_move": True,
        "watch_interval": 2,
        "custom_rules": [],
        "recursive": False,
    }


def get_categories(config: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Get category mappings from config or defaults."""
    if config and "categories" in config:
        return config["categories"]
    return DEFAULT_CATEGORIES.copy()


def get_excluded_dirs(config: dict[str, Any] | None = None) -> list[str]:
    """Get excluded directory names from config."""
    if config and "excluded_dirs" in config:
        return config["excluded_dirs"]
    return DEFAULT_EXCLUDED_DIRS.copy()


def add_custom_rule(
    config: dict[str, Any],
    rule_type: str,
    pattern: str,
    category: str,
    subfolder: str = "",
) -> dict[str, Any]:
    """Add a custom classification rule to config."""
    if "custom_rules" not in config:
        config["custom_rules"] = []
    config["custom_rules"].append({
        "type": rule_type,
        "pattern": pattern,
        "category": category,
        "subfolder": subfolder,
    })
    return config
