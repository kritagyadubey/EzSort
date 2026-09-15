"""Utility functions for EzSort."""

from __future__ import annotations

import platform
import sys
from pathlib import Path


def supports_color() -> bool:
    """Check if the terminal supports color output."""
    if platform.system() == "Windows":
        try:
            import os
            return os.environ.get("ANSICON") is not None or (
                "WT_SESSION" in os.environ
            ) or sys.stdout.isatty()
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def colorize(text: str, code: str) -> str:
    """Wrap text in ANSI color codes if supported."""
    if supports_color():
        return f"\033[{code}m{text}\033[0m"
    return text


def green(text: str) -> str:
    return colorize(text, "32")


def red(text: str) -> str:
    return colorize(text, "31")


def yellow(text: str) -> str:
    return colorize(text, "33")


def cyan(text: str) -> str:
    return colorize(text, "36")


def bold(text: str) -> str:
    return colorize(text, "1")


def get_unique_destination(destination: Path) -> Path:
    """Return a unique file path, avoiding overwrites.

    For 'report.pdf' that already exists, returns 'report (1).pdf',
    then 'report (2).pdf', etc. Preserves complex extensions correctly.
    """
    if not destination.exists():
        return destination

    parent = destination.parent
    stem = destination.stem
    suffix = destination.suffix

    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1
        if counter > 10000:
            raise RuntimeError(
                f"Could not find unique name for {destination} after 10000 attempts"
            )


def format_size(size_bytes: int) -> str:
    """Format a file size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def is_within_directory(directory: Path, target: Path) -> bool:
    """Check if target is within the given directory."""
    try:
        target.relative_to(directory)
        return True
    except ValueError:
        return False
