"""History tracking and undo support."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ezsort.config import get_history_path
from ezsort.models import OperationResult
from ezsort.utils import atomic_write_json, backup_corrupt_file, path_exists

logger = logging.getLogger(__name__)


def _load_history() -> list[dict]:
    """Load history from disk (corrupt files are backed up, not deleted)."""
    history_path = get_history_path()
    if history_path.exists():
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            raise ValueError("history root must be a JSON array")
        except (ValueError, OSError):
            backup_corrupt_file(history_path)
            logger.warning(
                "History file was unreadable; moved aside and starting fresh."
            )
            return []
    return []


def _save_history(history: list[dict]) -> None:
    """Save history to disk atomically."""
    history_path = get_history_path()
    atomic_write_json(history_path, history)


def _next_batch_id(history: list[dict]) -> str:
    """Generate a collision-free sequential batch ID like ``007``.

    Uses max(existing IDs) + 1 rather than ``len(history) + 1`` so clearing
    or removing batches can never produce duplicate IDs.
    """
    highest = 0
    for batch in history:
        try:
            highest = max(highest, int(str(batch.get("batch_id", "0"))))
        except (TypeError, ValueError):
            continue
    return f"{highest + 1:03d}"


def record_operations(
    results: list[OperationResult],
    folder: str | None = None,
) -> str:
    """Record operation results to history.

    Successful moves are stored as undoable operations; failed moves are
    stored too (with their error) so users can see what went wrong.

    Returns:
        The batch operation ID.
    """
    history = _load_history()
    timestamp = datetime.now(timezone.utc).isoformat()
    batch_id = _next_batch_id(history)

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    batch_entry: dict[str, Any] = {
        "batch_id": batch_id,
        "timestamp": timestamp,
        "operations": [],
        "total_moved": len(successful),
        "total_failed": len(failed),
    }
    if folder:
        batch_entry["folder"] = str(folder)

    for result in results:
        op = result.operation
        entry = {
            "operation_id": op.operation_id,
            "source": str(op.source),
            "destination": str(op.destination),
            "category": op.category,
            "reason": op.reason,
            "status": "moved" if result.success else "failed",
        }
        if not result.success and result.error:
            entry["error"] = result.error
        batch_entry["operations"].append(entry)

    history.append(batch_entry)
    _save_history(history)

    logger.info(
        "Recorded batch %s: %d moved, %d failed",
        batch_id,
        len(successful),
        len(failed),
    )
    return batch_id


def get_history() -> list[dict]:
    """Get the full operation history."""
    return _load_history()


def get_batch(batch_id: str) -> dict | None:
    """Get a specific batch by ID."""
    history = _load_history()
    for batch in history:
        if str(batch.get("batch_id")) == str(batch_id):
            return batch
    return None


def undo_last() -> tuple[bool, str]:
    """Undo the most recent batch of operations.

    Returns:
        Tuple of (success, message).
    """
    history = _load_history()
    if not history:
        return False, "No operations to undo."

    # Find the newest batch that still contains operations to reverse.
    index = len(history) - 1
    while index >= 0 and not history[index].get("operations"):
        index -= 1
    if index < 0:
        history = [b for b in history if b.get("operations")]
        _save_history(history)
        return False, "No operations to undo."

    return _undo_batch_at(history, index)


def undo_batch(batch_id: str) -> tuple[bool, str]:
    """Undo a specific batch by ID."""
    history = _load_history()
    for i, batch in enumerate(history):
        if str(batch.get("batch_id")) == str(batch_id):
            if not batch.get("operations"):
                return False, f"Batch {batch_id} has no operations to undo."
            return _undo_batch_at(history, i)
    return False, f"Batch {batch_id} not found in history."


def _undo_batch_at(history: list[dict], index: int) -> tuple[bool, str]:
    """Undo the batch at *index* inside *history*, then persist the result.

    Safety rules:
      * Never overwrite an existing file at the original location.
      * Entries that could not be restored stay in history so the user can
        retry or investigate; entries that were restored are removed.
      * A missing destination (file vanished or already restored) is
        reported and dropped, because retrying can never succeed.
    """
    batch = history[index]
    operations = batch.get("operations", [])

    restored = 0
    conflicts: list[str] = []
    missing: list[str] = []
    other_errors: list[str] = []
    remaining: list[dict] = []

    # Reverse order: last move is undone first.
    for op in reversed(operations):
        source = Path(op.get("source", ""))
        dest = Path(op.get("destination", ""))
        name = dest.name or str(dest)

        if op.get("status") == "failed":
            # Nothing was moved for failed entries - just drop them.
            continue

        if not path_exists(dest):
            # File is gone (deleted by user or already restored).
            missing.append(name)
            continue

        if path_exists(source):
            # Something already lives at the original location.
            # Never overwrite it - keep the record for a later retry.
            conflicts.append(
                f"{name}: original location is occupied by "
                f"{'a folder' if source.is_dir() else 'another file'}"
            )
            remaining.append(op)
            continue

        try:
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(source))
            restored += 1
            logger.info("Restored: %s -> %s", dest.name, source.name)
        except OSError as e:
            other_errors.append(f"Could not restore {name}: {e}")
            remaining.append(op)

    # Persist: remove restored entries, keep the ones that still need work.
    if remaining:
        batch = dict(batch)
        batch["operations"] = list(reversed(remaining))
        batch["total_moved"] = len(remaining)
        history[index] = batch
    else:
        history.pop(index)
    _save_history(history)

    problems = conflicts + other_errors + [
        f"{name}: file no longer exists at destination" for name in missing
    ]

    msg = f"Restored {restored} file(s)"
    if missing:
        msg += f", {len(missing)} already gone"
    if problems:
        msg += f"; {len(problems)} problem(s): " + "; ".join(problems)
        if conflicts:
            msg += (
                " (conflicting files were left untouched; run undo again "
                "after resolving them)"
            )

    # Success means everything that could be restored was restored.
    success = not conflicts and not other_errors
    return success, msg


def clear_history() -> None:
    """Clear all history."""
    _save_history([])
    logger.info("History cleared.")


def history_stats() -> dict[str, Any]:
    """Aggregate statistics derived from history."""
    history = _load_history()
    total_moved = 0
    total_failed = 0
    categories: dict[str, int] = {}
    for batch in history:
        total_moved += int(batch.get("total_moved", 0) or 0)
        total_failed += int(batch.get("total_failed", 0) or 0)
        for op in batch.get("operations", []):
            if op.get("status") == "failed":
                continue
            cat = str(op.get("category", "Others")).split("/")[0]
            categories[cat] = categories.get(cat, 0) + 1
    return {
        "batches": len(history),
        "total_moved": total_moved,
        "total_failed": total_failed,
        "categories": categories,
    }


def remove_batch(batch_id: str) -> bool:
    """Delete a single batch from history. Returns True if found."""
    history = _load_history()
    new_history = [b for b in history if str(b.get("batch_id")) != str(batch_id)]
    if len(new_history) == len(history):
        return False
    _save_history(new_history)
    return True
