"""History tracking and undo support."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ezsort.config import get_history_path
from ezsort.models import OperationResult

logger = logging.getLogger(__name__)


def _load_history() -> list[dict]:
    """Load history from disk."""
    history_path = get_history_path()
    if history_path.exists():
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_history(history: list[dict]) -> None:
    """Save history to disk."""
    history_path = get_history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def record_operations(results: list[OperationResult]) -> str:
    """Record successful operations to history.

    Returns:
        The batch operation ID.
    """
    history = _load_history()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Generate batch ID from timestamp
    batch_id = f"{len(history) + 1:03d}"

    successful = [r for r in results if r.success]

    batch_entry = {
        "batch_id": batch_id,
        "timestamp": timestamp,
        "operations": [],
        "total_moved": len(successful),
    }

    for result in successful:
        op = result.operation
        batch_entry["operations"].append({
            "operation_id": op.operation_id,
            "source": str(op.source),
            "destination": str(op.destination),
            "category": op.category,
            "reason": op.reason,
        })

    history.append(batch_entry)
    _save_history(history)

    logger.info("Recorded %d operations with batch ID %s", len(successful), batch_id)
    return batch_id


def get_history() -> list[dict]:
    """Get the full operation history."""
    return _load_history()


def get_batch(batch_id: str) -> dict | None:
    """Get a specific batch by ID."""
    history = _load_history()
    for batch in history:
        if batch.get("batch_id") == batch_id:
            return batch
    return None


def undo_last() -> tuple[bool, str]:
    """Undo the last batch of operations.

    Returns:
        Tuple of (success, message).
    """
    history = _load_history()
    if not history:
        return False, "No operations to undo."

    last_batch = history[-1]
    operations = last_batch.get("operations", [])

    if not operations:
        history.pop()
        _save_history(history)
        return True, "Batch had no operations."

    restored = 0
    errors = []

    for op in reversed(operations):
        source = Path(op["source"])
        dest = Path(op["destination"])

        try:
            if not dest.exists():
                errors.append(f"File not found: {dest.name}")
                continue

            # Ensure source parent directory exists
            source.parent.mkdir(parents=True, exist_ok=True)

            # Move file back
            shutil.move(str(dest), str(source))
            restored += 1
            logger.info("Restored: %s -> %s", dest.name, source.name)

        except (OSError, PermissionError) as e:
            errors.append(f"Could not restore {dest.name}: {e}")

    # Remove the batch from history
    history.pop()
    _save_history(history)

    msg = f"Restored {restored} file(s)"
    if errors:
        msg += f" with {len(errors)} error(s): {'; '.join(errors)}"

    return True, msg


def clear_history() -> None:
    """Clear all history."""
    _save_history([])
    logger.info("History cleared.")
