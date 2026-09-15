"""File scanner - discovers files in a directory."""

from __future__ import annotations

import logging
from pathlib import Path

from ezsort.models import FileItem, ScanReport
from ezsort.config import get_excluded_dirs

logger = logging.getLogger(__name__)


def scan_directory(
    directory: Path,
    recursive: bool = False,
    excluded_dirs: list[str] | None = None,
) -> list[FileItem]:
    """Scan a directory and return discovered files.

    Args:
        directory: The directory to scan.
        recursive: Whether to scan subdirectories.
        excluded_dirs: Directory names to skip.

    Returns:
        List of FileItem objects for discovered files.
    """
    if excluded_dirs is None:
        excluded_dirs = get_excluded_dirs()

    files: list[FileItem] = []

    if not directory.exists():
        logger.warning("Directory does not exist: %s", directory)
        return files

    if not directory.is_dir():
        logger.warning("Path is not a directory: %s", directory)
        return files

    try:
        entries = sorted(directory.iterdir())
    except PermissionError:
        logger.error("Permission denied: %s", directory)
        return files

    for entry in entries:
        name = entry.name

        # Skip hidden files
        if name.startswith("."):
            continue

        # Skip excluded directories
        if entry.is_dir() and name in excluded_dirs:
            logger.debug("Skipping excluded directory: %s", name)
            continue

        # Skip symlinks by default
        if entry.is_symlink():
            logger.debug("Skipping symlink: %s", name)
            continue

        # Record directories but don't process them as files
        if entry.is_dir():
            if recursive:
                sub_files = scan_directory(entry, recursive=True, excluded_dirs=excluded_dirs)
                files.extend(sub_files)
            continue

        # Process files
        if entry.is_file():
            item = FileItem(path=entry)
            files.append(item)
            logger.debug("Found file: %s", name)

    return files


def scan_for_report(
    directory: Path,
    recursive: bool = False,
    excluded_dirs: list[str] | None = None,
) -> ScanReport:
    """Scan and produce a summary report."""
    files = scan_directory(directory, recursive=recursive, excluded_dirs=excluded_dirs)

    report = ScanReport(total_files=len(files))

    # Count directories
    try:
        for entry in directory.iterdir():
            if entry.is_dir() and not entry.is_symlink():
                report.directories += 1
    except OSError:
        pass

    # Count symlinks
    for entry in directory.iterdir():
        if entry.is_symlink():
            report.symlinks += 1

    return report
