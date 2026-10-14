"""Planner - creates the operation plan from classified files."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ezsort.models import FileItem, Operation
from ezsort.utils import is_within_directory, path_exists, sanitize_relative_path

logger = logging.getLogger(__name__)


@dataclass
class PlanResult:
    """Detailed outcome of planning."""

    operations: list[Operation] = field(default_factory=list)
    #: (file path, reason) entries that were deliberately not planned.
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def _category_destination(
    target_directory: Path,
    category: str,
    filename: str,
) -> Path | None:
    """Build a safe destination path, or None if the category is unusable.

    Every category segment is sanitized, so a hostile or broken custom rule
    such as ``../../Windows`` can never place files outside the target
    folder.
    """
    clean = sanitize_relative_path(category)
    parts = [p for p in clean.split("/") if p]
    if not parts:
        return None
    dest = target_directory
    for part in parts:
        dest = dest / part
    dest = dest / filename

    # Defense in depth: the final path must live inside the target folder.
    if not is_within_directory(target_directory, dest):
        return None
    return dest


def create_plan_detailed(
    classified_files: list[tuple[FileItem, str, str]],
    target_directory: Path,
) -> PlanResult:
    """Create an operation plan plus a list of intentionally skipped files.

    Skips:
      * files whose destination equals their current location
        (already organized - makes repeated runs idempotent),
      * files that already live anywhere inside their own category folder
        (recursive runs never shuffle organized files back and forth),
      * files whose category cannot be turned into a safe destination.
    """
    result = PlanResult()
    # Resolve target once for robust comparisons.
    try:
        target_resolved = target_directory.resolve()
    except OSError:  # pragma: no cover - extremely rare
        target_resolved = target_directory

    for file_item, category, reason in classified_files:
        source = file_item.path

        # Destination directory for this category (e.g. target/Images)
        clean = sanitize_relative_path(category)
        parts = [p for p in clean.split("/") if p]
        if not parts:
            result.skipped.append((source, "Category name is not usable"))
            continue

        category_root = target_resolved / parts[0]

        # Resolve source once for robust comparisons.
        try:
            source_resolved = source.resolve()
        except OSError:  # pragma: no cover
            source_resolved = source

        # Already inside its own category folder (incl. subfolders)?
        # Keeps recursive runs idempotent: organized files are never
        # shuffled back out or renamed again.
        if is_within_directory(category_root, source_resolved):
            logger.debug("Skipping %s - already organized", source.name)
            result.skipped.append((source, "Already inside its category folder"))
            continue

        dest_path = _category_destination(target_directory, category, source.name)
        if dest_path is None:
            result.skipped.append((source, f"Unsafe category: {category!r}"))
            continue

        # Skip if source and destination are the same file.
        try:
            if source.resolve() == dest_path.resolve():
                logger.debug("Skipping %s - already in correct location", source.name)
                result.skipped.append((source, "Already in correct location"))
                continue
        except OSError:
            pass

        collision = path_exists(dest_path)
        if collision:
            # Preview shows the real final name the file will get.
            from ezsort.utils import get_unique_destination

            final = get_unique_destination(dest_path)
            logger.debug(
                "Planned with rename: %s -> %s (name conflict)",
                source.name,
                final,
            )
            op = Operation(
                source=source,
                destination=dest_path,
                category=category,
                reason=reason,
                collision=True,
            )
            result.operations.append(op)
            continue

        op = Operation(
            source=source,
            destination=dest_path,
            category=category,
            reason=reason,
        )
        result.operations.append(op)
        logger.debug(
            "Planned: %s -> %s (%s)",
            source.name,
            dest_path,
            category,
        )

    return result


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
    return create_plan_detailed(classified_files, target_directory).operations
