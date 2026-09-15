"""Planner - creates the operation plan from classified files."""

from __future__ import annotations

import logging
from pathlib import Path

from ezsort.models import FileItem, Operation

logger = logging.getLogger(__name__)


def create_plan(
    classified_files: list[tuple[FileItem, str, str]],
    target_directory: Path,
) -> list[Operation]:
    """Create an operation plan from classified files.

    Args:
        classified_files: List of (FileItem, category, reason) tuples.
        target_directory: The directory being organized.

    Returns:
        List of Operation objects representing planned moves.
    """
    operations: list[Operation] = []

    for file_item, category, reason in classified_files:
        # Parse category for subfolder support (e.g., "Documents/Invoices")
        parts = category.split("/", 1)
        main_category = parts[0]
        subfolder = parts[1] if len(parts) > 1 else ""

        # Build destination path
        dest_dir = target_directory / main_category
        if subfolder:
            dest_dir = dest_dir / subfolder

        dest_path = dest_dir / file_item.path.name

        # Skip if source and destination are the same
        try:
            if file_item.path.resolve() == dest_path.resolve():
                logger.debug("Skipping %s - already in correct location", file_item.path.name)
                continue
        except OSError:
            pass

        op = Operation(
            source=file_item.path,
            destination=dest_path,
            category=category,
            reason=reason,
        )
        operations.append(op)
        logger.debug(
            "Planned: %s -> %s (%s)",
            file_item.path.name,
            dest_path,
            category,
        )

    return operations
