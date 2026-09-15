"""Duplicate file detection using SHA-256 hashing."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192


def compute_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file, reading in chunks.

    Args:
        file_path: Path to the file to hash.

    Returns:
        Hex digest of the file's SHA-256 hash.
    """
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, IOError) as e:
        logger.error("Could not hash %s: %s", file_path, e)
        return ""


def find_duplicates(
    files: list[Path],
    quick: bool = True,
) -> dict[str, list[Path]]:
    """Find duplicate files by content hash.

    Args:
        files: List of file paths to check.
        quick: If True, compare by size first (faster).

    Returns:
        Dictionary mapping hash -> list of paths with that hash.
        Only includes groups with more than one file.
    """
    # Group by size first for quick filtering
    size_groups: dict[int, list[Path]] = {}
    for f in files:
        try:
            size = f.stat().st_size
            size_groups.setdefault(size, []).append(f)
        except OSError:
            continue

    duplicates: dict[str, list[Path]] = {}

    for size, group in size_groups.items():
        if len(group) < 2:
            continue

        # Hash files in this size group
        hash_groups: dict[str, list[Path]] = {}
        for f in group:
            h = compute_hash(f)
            if h:
                hash_groups.setdefault(h, []).append(f)

        for h, paths in hash_groups.items():
            if len(paths) > 1:
                duplicates[h] = paths

    return duplicates


def get_duplicate_report(files: list[Path]) -> list[dict]:
    """Generate a duplicate report.

    Returns:
        List of dictionaries with hash, files, and size info.
    """
    duplicates = find_duplicates(files)
    report = []

    for h, paths in duplicates.items():
        try:
            size = paths[0].stat().st_size
        except OSError:
            size = 0
        report.append({
            "hash": h,
            "files": [str(p) for p in paths],
            "size": size,
            "count": len(paths),
        })

    return report
