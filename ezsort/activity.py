"""Persistent activity log.

The activity feed used to live only in memory, so closing the window threw
away the account of what happened. It is now stored next to the history in
``activity.json`` as a plain JSON array of entries. Entries keep the same
shape they always had (``time``, ``type``, ``message``), so older data and
any external reader stay compatible.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ezsort.config import get_activity_path
from ezsort.utils import atomic_write_json, backup_corrupt_file

logger = logging.getLogger(__name__)

MAX_ENTRIES = 500


def load_activity(limit: int = MAX_ENTRIES) -> list[dict[str, Any]]:
    """Load persisted activity entries (newest last)."""
    path = get_activity_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("activity root must be a JSON array")
        entries = [e for e in data if isinstance(e, dict)]
        return entries[-limit:]
    except (ValueError, OSError):
        backup_corrupt_file(path)
        logger.warning("Activity file was unreadable; moved aside.")
        return []


def save_activity(entries: list[dict[str, Any]]) -> None:
    """Persist the activity log atomically."""
    atomic_write_json(get_activity_path(), entries[-MAX_ENTRIES:])


def append_activity(entry: dict[str, Any], limit: int = MAX_ENTRIES) -> None:
    """Append one entry, trimming the oldest beyond *limit*."""
    entries = load_activity(limit)
    entries.append(dict(entry))
    save_activity(entries[-limit:])


def clear_activity() -> None:
    """Forget every persisted entry."""
    save_activity([])


def activity_path() -> Path:
    return get_activity_path()
