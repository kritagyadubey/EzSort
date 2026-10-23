"""File scanner - discovers files in a directory."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from ezsort.config import get_excluded_dirs
from ezsort.models import FileItem, ScanReport
from ezsort.utils import is_hidden

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Detailed result of a directory scan."""

    files: list[FileItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    hidden_skipped: int = 0
    symlink_skipped: int = 0
    dirs_skipped: int = 0


def _excluded(name: str, excluded_dirs: set[str]) -> bool:
    """Case-insensitive directory-name check (Windows folders are too).

    *excluded_dirs* must already be lowercased (computed once per scan).
    """
    return name.lower() in excluded_dirs


def scan_directory_ex(
    directory: Path,
    recursive: bool = False,
    excluded_dirs: list[str] | None = None,
    skip_hidden: bool = True,
) -> ScanResult:
    """Scan a directory and return files plus any errors encountered.

    Unlike :func:`scan_directory`, this never swallows problems: unreadable
    folders are reported in ``result.errors`` instead of disappearing.
    Symlinks are never followed, and excluded directories are skipped at
    every depth.
    """
    if excluded_dirs is None:
        excluded_dirs = get_excluded_dirs()

    result = ScanResult()

    if not directory.exists():
        result.errors.append(f"Directory does not exist: {directory}")
        return result
    if not directory.is_dir():
        result.errors.append(f"Not a directory: {directory}")
        return result

    # Lowercased once: the check runs for every directory we meet.
    excluded_lower = {d.lower() for d in excluded_dirs}

    # Iterative traversal: no recursion limit issues on very deep trees.
    pending: list[Path] = [directory]
    while pending:
        current = pending.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except PermissionError:
            result.errors.append(f"Permission denied: {current}")
            continue
        except OSError as e:
            result.errors.append(f"Cannot read {current}: {e}")
            continue

        for entry in entries:
            try:
                is_link = entry.is_symlink()
                if is_link:
                    # Never follow symbolic links - avoids escaping the tree.
                    result.symlink_skipped += 1
                    logger.debug("Skipping symlink: %s", entry.path)
                    continue

                if skip_hidden and is_hidden(Path(entry.path)):
                    result.hidden_skipped += 1
                    logger.debug("Skipping hidden: %s", entry.path)
                    continue

                if entry.is_dir(follow_symlinks=False):
                    if _excluded(entry.name, excluded_lower):
                        result.dirs_skipped += 1
                        logger.debug("Skipping excluded directory: %s", entry.name)
                        continue
                    if recursive:
                        pending.append(Path(entry.path))
                    continue

                if entry.is_file(follow_symlinks=False):
                    info = entry.stat(follow_symlinks=False)
                    result.files.append(FileItem(
                        path=Path(entry.path),
                        size=info.st_size,
                        extension=Path(entry.name).suffix.lower(),
                        probed=True,
                    ))
                    logger.debug("Found file: %s", entry.name)
            except OSError as e:
                result.errors.append(f"Cannot stat {entry.path}: {e}")

    result.files.sort(key=lambda item: str(item.path))
    return result


def scan_directory(
    directory: Path,
    recursive: bool = False,
    excluded_dirs: list[str] | None = None,
    skip_hidden: bool = True,
) -> list[FileItem]:
    """Scan a directory and return discovered files.

    Args:
        directory: The directory to scan.
        recursive: Whether to scan subdirectories.
        excluded_dirs: Directory names to skip.
        skip_hidden: Whether to skip hidden files/folders.

    Returns:
        List of FileItem objects for discovered files.
    """
    return scan_directory_ex(
        directory,
        recursive=recursive,
        excluded_dirs=excluded_dirs,
        skip_hidden=skip_hidden,
    ).files


def scan_for_report(
    directory: Path,
    recursive: bool = False,
    excluded_dirs: list[str] | None = None,
) -> ScanReport:
    """Scan and produce a summary report."""
    result = scan_directory_ex(
        directory, recursive=recursive, excluded_dirs=excluded_dirs
    )

    report = ScanReport(
        total_files=len(result.files),
        hidden=result.hidden_skipped,
        symlinks=result.symlink_skipped,
        errors=list(result.errors),
    )
    report.unreadable = len(result.errors)

    # Count directories (top level, robust against unreadable folders).
    try:
        for entry in os.scandir(directory):
            try:
                if entry.is_dir(follow_symlinks=False):
                    report.directories += 1
            except OSError:
                report.unreadable += 1
    except OSError as e:
        report.errors.append(f"Cannot read {directory}: {e}")

    return report
