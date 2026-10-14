"""Utility functions for EzSort."""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

from ezsort.constants import ILLEGAL_PATH_CHARS, WINDOWS_RESERVED_NAMES


def supports_color() -> bool:
    """Check if the terminal supports color output."""
    if platform.system() == "Windows":
        try:
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


def path_exists(path: Path) -> bool:
    """True if anything (file, dir, or broken symlink) exists at *path*.

    Unlike ``Path.exists()``, this also returns True for broken symbolic
    links, so collision detection never tries to write "through" a link.
    """
    try:
        return os.path.lexists(str(path))
    except OSError:
        return False


def get_unique_destination(destination: Path) -> Path:
    """Return a unique file path, avoiding overwrites.

    For 'report.pdf' that already exists, returns 'report (1).pdf',
    then 'report (2).pdf', etc. Preserves complex extensions correctly.
    """
    if not path_exists(destination):
        return destination

    parent = destination.parent
    stem = destination.stem
    suffix = destination.suffix

    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_path = parent / new_name
        if not path_exists(new_path):
            return new_path
        counter += 1
        if counter > 10000:
            raise RuntimeError(
                f"Could not find unique name for {destination} after 10000 attempts"
            )


def sanitize_path_segment(segment: str, fallback: str = "Other") -> str:
    """Turn an arbitrary string into a safe single folder-name segment.

    Removes path separators, traversal sequences (``..``), illegal
    characters, and Windows reserved device names so that a category
    coming from user configuration can never escape the target folder
    or create an invalid directory name.
    """
    text = str(segment).strip()
    # Drop anything that could act as a separator or traversal.
    text = text.replace("/", "").replace("\\", "")
    text = text.replace("\x00", "")
    for ch in ILLEGAL_PATH_CHARS:
        text = text.replace(ch, "_")
    text = text.strip(" .")  # Windows dislikes trailing dots/spaces
    if not text or text in (".", ".."):
        return fallback
    if text.lower() in WINDOWS_RESERVED_NAMES:
        text = f"{text}_"
    # Guard against absurd lengths (Windows MAX_PATH component limit).
    if len(text) > 100:
        text = text[:100].rstrip(" .")
    return text or fallback


def sanitize_relative_path(path_str: str) -> str:
    """Sanitize a possibly nested category path like ``Documents/Invoices``.

    Every segment is sanitized independently so ``../../etc`` collapses
    into a harmless single-level folder name chain.
    """
    parts = [p for p in str(path_str).replace("\\", "/").split("/") if p]
    clean = [sanitize_path_segment(p) for p in parts]
    return "/".join(clean) if clean else "Others"


def ensure_long_path(path: Path) -> str:
    """Return a path string safe for long Windows paths (> 260 chars).

    On other platforms (or short paths) the plain string is returned.
    """
    text = str(path)
    if platform.system() != "Windows":
        return text
    if len(text) < 240:
        return text
    if text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        # UNC path: \\server\share\... -> \\?\UNC\server\share\...
        return "\\\\?\\UNC\\" + text[2:]
    return "\\\\?\\" + text


def is_within_directory(directory: Path, target: Path) -> bool:
    """Check if target is within the given directory (best effort).

    Falls back to a normalized string comparison when the paths cannot be
    resolved (e.g. destinations that do not exist yet).
    """
    try:
        target.relative_to(directory)
        return True
    except ValueError:
        pass
    try:
        target.resolve(strict=False).relative_to(directory.resolve(strict=False))
        return True
    except (OSError, ValueError):
        return False


def format_size(size_bytes: int) -> str:
    """Format a file size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON to *path* atomically so a crash never corrupts the file.

    Writes to a temporary file in the same directory and swaps it in with
    ``os.replace`` (atomic on both Windows and POSIX).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def backup_corrupt_file(path: Path) -> Path | None:
    """Move an unreadable file aside so it can be inspected later.

    Returns the backup path, or None if the move failed.
    """
    try:
        if not path_exists(path):
            return None
        backup = path.with_name(path.name + ".corrupt")
        counter = 1
        while path_exists(backup):
            backup = path.with_name(f"{path.name}.corrupt.{counter}")
            counter += 1
        os.replace(str(path), str(backup))
        return backup
    except OSError:
        return None


def is_hidden(path: Path) -> bool:
    """True if *path* looks hidden (dot-prefix or Windows hidden attribute)."""
    name = path.name
    if name.startswith("."):
        return True
    if platform.system() == "Windows" and name:
        try:
            import ctypes

            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))  # type: ignore[attr-defined]
            if attrs != -1 and attrs & 0x2:  # FILE_ATTRIBUTE_HIDDEN
                return True
        except Exception:
            pass
    return False
