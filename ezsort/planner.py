"""Planner - creates the operation plan from classified files."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from ezsort.models import FileItem, Operation
from ezsort.utils import path_exists, sanitize_relative_path

logger = logging.getLogger(__name__)


@dataclass
class PlanResult:
    """Detailed outcome of planning."""

    operations: list[Operation] = field(default_factory=list)
    #: (file path, reason) entries that were deliberately not planned.
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def _category_destination(
    target_directory: Path,
    parts: list[str],
    filename: str,
) -> Path | None:
    """Build a safe destination path, or None if the category is unusable.

    ``parts`` are already-sanitized category segments, so they cannot
    contain separators or traversal. The containment check is a plain
    normalized string comparison - no filesystem calls - because the
    planner resolves the target once.
    """
    if not parts:
        return None
    dest = Path(os.path.join(str(target_directory), *parts, filename))
    target_norm = os.path.normcase(str(target_directory))
    dest_norm = os.path.normcase(str(dest))
    if not (dest_norm == target_norm
            or dest_norm.startswith(target_norm + os.sep)):
        return None
    return dest


def _resolved_source(
    source: Path,
    target_abs: str,
    target_resolved: Path,
) -> Path:
    """Resolve a source path without a filesystem round-trip when possible.

    The scanner builds every source from the target folder, so the common
    case is purely lexical: map the relative part onto the already-resolved
    target. This keeps planning O(n) instead of calling ``Path.resolve()``
    several times per file (which made a 10k-file preview take minutes).
    """
    source_abs = os.path.abspath(str(source))
    target_norm = os.path.normcase(target_abs)
    source_norm = os.path.normcase(source_abs)
    if source_norm == target_norm:
        return target_resolved
    prefix = target_norm + os.sep
    if source_norm.startswith(prefix):
        relative = source_abs[len(target_abs) + 1:]
        return Path(os.path.join(str(target_resolved), relative))
    try:
        return source.resolve()
    except OSError:  # pragma: no cover - extremely rare
        return source


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
    # Resolve the target once; every source path is derived from it.
    try:
        target_resolved = target_directory.resolve()
    except OSError:  # pragma: no cover - extremely rare
        target_resolved = target_directory
    target_abs = os.path.abspath(str(target_directory))

    for file_item, category, reason in classified_files:
        source = file_item.path

        # Destination directory for this category (e.g. target/Images)
        clean = sanitize_relative_path(category)
        parts = [p for p in clean.split("/") if p]
        if not parts:
            result.skipped.append((source, "Category name is not usable"))
            continue

        category_root = Path(os.path.join(str(target_resolved), parts[0]))

        source_resolved = _resolved_source(
            source, target_abs, target_resolved,
        )

        # Already inside its own category folder (incl. subfolders)?
        # Keeps recursive runs idempotent: organized files are never
        # shuffled back out or renamed again.
        source_norm = os.path.normcase(str(source_resolved))
        root_norm = os.path.normcase(str(category_root))
        if (source_norm == root_norm
                or source_norm.startswith(root_norm + os.sep)):
            logger.debug("Skipping %s - already organized", source.name)
            result.skipped.append((source, "Already inside its category folder"))
            continue

        dest_path = _category_destination(target_resolved, parts, source.name)
        if dest_path is None:
            result.skipped.append((source, f"Unsafe category: {category!r}"))
            continue

        # Skip if source and destination are the same file.
        if source_norm == os.path.normcase(str(dest_path)):
            logger.debug("Skipping %s - already in correct location", source.name)
            result.skipped.append((source, "Already in correct location"))
            continue

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
