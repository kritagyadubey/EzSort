"""File organizer - executes the planned operations."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ezsort.models import Operation, OperationResult
from ezsort.utils import ensure_long_path, get_unique_destination, path_exists

logger = logging.getLogger(__name__)

#: Progress callback: (completed_count, total_count, operation)
ProgressCallback = Callable[[int, int, Operation], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def execute_operations(
    operations: list[Operation],
    dry_run: bool = False,
    progress: Optional[ProgressCallback] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> list[OperationResult]:
    """Execute a list of operations.

    Args:
        operations: List of Operation objects.
        dry_run: If True, don't actually move files.
        progress: Optional callback invoked after each operation with
            ``(completed, total, operation)``.
        cancel_check: Optional callable; when it returns True the remaining
            operations are skipped (already-executed ones stay executed).

    Returns:
        List of OperationResult objects (same order as *operations*).
    """
    results: list[OperationResult] = []
    total = len(operations)

    for index, op in enumerate(operations, start=1):
        if cancel_check is not None and cancel_check():
            logger.info("Execution cancelled after %d/%d operations", index - 1, total)
            break
        result = execute_single(op, dry_run=dry_run)
        results.append(result)
        if progress is not None:
            try:
                progress(index, total, result.operation)
            except Exception:  # pragma: no cover - progress must never break runs
                logger.debug("Progress callback raised", exc_info=True)

    return results


def execute_single(
    operation: Operation,
    dry_run: bool = False,
) -> OperationResult:
    """Execute a single operation.

    Safety guarantees:
      * directories are never moved (only regular files),
      * an existing file at the destination is never overwritten - the
        incoming file gets a `` (n)`` suffix instead,
      * the source is verified immediately before the move so a vanished
        file is reported accurately instead of half-succeeding.

    Args:
        operation: The Operation to execute.
        dry_run: If True, don't actually move the file.

    Returns:
        OperationResult indicating success or failure.
    """
    timestamp = _now()

    if dry_run:
        logger.info(
            "[DRY RUN] Would move: %s -> %s",
            operation.source.name,
            operation.destination,
        )
        return OperationResult(
            operation=operation,
            success=True,
            timestamp=timestamp,
        )

    try:
        # 1. Validate the source before touching anything.
        if not path_exists(operation.source):
            return _failure(
                operation,
                f"Source file no longer exists: {operation.source}",
                timestamp,
            )
        try:
            if operation.source.is_dir():
                return _failure(
                    operation,
                    f"Source is a directory, refusing to move it: "
                    f"{operation.source.name}",
                    timestamp,
                )
        except OSError as e:
            return _failure(operation, f"Cannot inspect source: {e}", timestamp)

        # 2. Ensure destination directory exists (long-path safe).
        try:
            Path(ensure_long_path(operation.destination.parent)).mkdir(
                parents=True, exist_ok=True
            )
        except OSError as e:
            return _failure(
                operation,
                f"Cannot create destination folder "
                f"{operation.destination.parent}: {e}",
                timestamp,
            )

        # 3. Never overwrite: re-check the destination right before moving.
        try:
            final_dest = get_unique_destination(operation.destination)
        except RuntimeError as e:
            return _failure(operation, str(e), timestamp)

        if final_dest != operation.destination:
            logger.info(
                "File already exists at %s, renaming to %s",
                operation.destination.name,
                final_dest.name,
            )

        # 4. Move the file.
        shutil.move(
            ensure_long_path(operation.source),
            ensure_long_path(final_dest),
        )

        logger.info("Moved: %s -> %s", operation.source.name, final_dest.name)

        moved_op = Operation(
            source=operation.source,
            destination=final_dest,
            category=operation.category,
            reason=operation.reason,
            operation_id=operation.operation_id,
            collision=operation.collision or final_dest != operation.destination,
        )
        return OperationResult(
            operation=moved_op,
            success=True,
            timestamp=timestamp,
        )

    except PermissionError as e:
        return _failure(
            operation,
            f"Permission denied while moving {operation.source.name}: {e}",
            timestamp,
        )
    except OSError as e:
        return _failure(
            operation,
            f"OS error while moving {operation.source.name} -> "
            f"{operation.destination.parent}: {e}",
            timestamp,
        )
    except Exception as e:  # unexpected, but must not abort the whole batch
        logger.exception("Unexpected error moving %s", operation.source)
        return _failure(
            operation,
            f"Unexpected error moving {operation.source.name}: {e}",
            timestamp,
        )


def _failure(operation: Operation, error: str, timestamp: str) -> OperationResult:
    logger.error("Failed to move %s: %s", operation.source.name, error)
    return OperationResult(
        operation=operation,
        success=False,
        error=error,
        timestamp=timestamp,
    )
