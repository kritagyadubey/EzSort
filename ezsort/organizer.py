"""File organizer - executes the planned operations."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ezsort.models import Operation, OperationResult
from ezsort.utils import get_unique_destination

logger = logging.getLogger(__name__)


def execute_operations(
    operations: list[Operation],
    dry_run: bool = False,
) -> list[OperationResult]:
    """Execute a list of operations.

    Args:
        operations: List of Operation objects.
        dry_run: If True, don't actually move files.

    Returns:
        List of OperationResult objects.
    """
    results: list[OperationResult] = []

    for op in operations:
        result = execute_single(op, dry_run=dry_run)
        results.append(result)

    return results


def execute_single(
    operation: Operation,
    dry_run: bool = False,
) -> OperationResult:
    """Execute a single operation.

    Args:
        operation: The Operation to execute.
        dry_run: If True, don't actually move the file.

    Returns:
        OperationResult indicating success or failure.
    """
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()

    if dry_run:
        logger.info("[DRY RUN] Would move: %s -> %s", operation.source.name, operation.destination)
        return OperationResult(
            operation=operation,
            success=True,
            timestamp=timestamp,
        )

    try:
        # Ensure destination directory exists
        operation.destination.parent.mkdir(parents=True, exist_ok=True)

        # Check for existing file and get unique destination
        final_dest = get_unique_destination(operation.destination)

        # If destination was renamed due to conflict, update the operation
        if final_dest != operation.destination:
            logger.info(
                "File already exists at %s, renaming to %s",
                operation.destination.name,
                final_dest.name,
            )

        # Move the file
        shutil.move(str(operation.source), str(final_dest))

        logger.info("Moved: %s -> %s", operation.source.name, final_dest.name)

        return OperationResult(
            operation=Operation(
                source=operation.source,
                destination=final_dest,
                category=operation.category,
                reason=operation.reason,
                operation_id=operation.operation_id,
            ),
            success=True,
            timestamp=timestamp,
        )

    except PermissionError as e:
        error_msg = f"Permission denied: {e}"
        logger.error("Failed to move %s: %s", operation.source.name, error_msg)
        return OperationResult(
            operation=operation,
            success=False,
            error=error_msg,
            timestamp=timestamp,
        )

    except OSError as e:
        error_msg = f"OS error: {e}"
        logger.error("Failed to move %s: %s", operation.source.name, error_msg)
        return OperationResult(
            operation=operation,
            success=False,
            error=error_msg,
            timestamp=timestamp,
        )

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error("Failed to move %s: %s", operation.source.name, error_msg)
        return OperationResult(
            operation=operation,
            success=False,
            error=error_msg,
            timestamp=timestamp,
        )
