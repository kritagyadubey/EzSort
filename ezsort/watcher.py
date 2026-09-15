"""Watch mode - monitors a directory for new files."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from ezsort.scanner import scan_directory
from ezsort.classifier import classify_file
from ezsort.planner import create_plan
from ezsort.organizer import execute_operations
from ezsort.models import FileItem

logger = logging.getLogger(__name__)


def watch_directory(
    directory: Path,
    interval: int = 2,
    recursive: bool = False,
    config: dict | None = None,
    on_move: Callable[[str], None] | None = None,
) -> None:
    """Watch a directory and organize new files as they appear.

    Args:
        directory: Directory to watch.
        interval: Seconds between scans.
        recursive: Whether to watch subdirectories.
        config: Optional configuration.
        on_move: Optional callback when a file is moved.
    """
    import sys

    print(f"\n  EzSort Watch Mode")
    print(f"  Watching: {directory}")
    print(f"  Press Ctrl+C to stop\n")

    known_files: set[Path] = set()

    # Record existing files
    try:
        for entry in directory.iterdir():
            if entry.is_file() and not entry.is_symlink():
                known_files.add(entry.resolve())
    except OSError as e:
        logger.error("Cannot watch directory: %s", e)
        return

    try:
        while True:
            time.sleep(interval)

            try:
                current_files: set[Path] = set()
                for entry in directory.iterdir():
                    if entry.is_file() and not entry.is_symlink():
                        current_path = entry.resolve()
                        current_files.add(current_path)

                        # New file detected
                        if current_path not in known_files:
                            _handle_new_file(entry, directory, config, on_move)

                known_files = current_files

            except OSError as e:
                logger.error("Error scanning directory: %s", e)
                continue

    except KeyboardInterrupt:
        print("\n  Watch mode stopped.")


def _handle_new_file(
    file_path: Path,
    target_dir: Path,
    config: dict | None,
    on_move: Callable[[str], None] | None,
) -> None:
    """Handle a newly detected file."""
    # Brief wait in case file is still being written
    time.sleep(0.5)

    if not file_path.exists():
        return

    item = FileItem(path=file_path)
    category, reason = classify_file(item, config)

    print(f"  New file detected: {file_path.name}")
    print(f"  -> {category}/{file_path.name}")

    # Create and execute plan
    classified = [(item, category, reason)]
    plan = create_plan(classified, target_dir)
    results = execute_operations(plan, dry_run=False)

    if results and results[0].success:
        print(f"  Moved successfully.\n")
        if on_move:
            on_move(f"Moved {file_path.name} to {category}/")
    else:
        error = results[0].error if results else "Unknown error"
        print(f"  Failed: {error}\n")
