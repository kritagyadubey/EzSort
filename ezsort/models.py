"""Data models for EzSort operations."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FileItem:
    """Represents a discovered file."""

    path: Path
    size: int = 0
    extension: str = ""
    is_symlink: bool = False
    is_dir: bool = False
    #: True when the caller already filled every field from a DirEntry.
    #: Skips four filesystem probes per file during large scans.
    probed: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.probed:
            return
        try:
            exists = self.path.exists()
        except OSError:
            exists = False
        if not self.extension and exists:
            self.extension = self.path.suffix.lower()
        if self.size == 0 and exists:
            try:
                self.size = self.path.stat().st_size
            except OSError:
                self.size = 0
        try:
            self.is_symlink = self.path.is_symlink()
            self.is_dir = self.path.is_dir()
        except OSError:
            self.is_symlink = False
            self.is_dir = False


@dataclass
class Operation:
    """Represents a single file operation (move)."""

    source: Path
    destination: Path
    category: str
    reason: str
    operation_id: str = ""
    #: True when the destination name was adjusted at plan time because a
    #: file with the same name already exists there.
    collision: bool = False

    def __post_init__(self) -> None:
        if not self.operation_id:
            # Include a timestamp + random suffix so two runs that move the
            # same source path never produce colliding operation IDs.
            seed = f"{self.source}|{_utc_now_iso()}|{uuid.uuid4().hex}"
            self.operation_id = hashlib.sha256(seed.encode()).hexdigest()[:12]


@dataclass
class OperationResult:
    """Result of executing an operation."""

    operation: Operation
    success: bool
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


@dataclass
class ScanReport:
    """Results of scanning a directory."""

    total_files: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    duplicates: int = 0
    organizable: int = 0
    symlinks: int = 0
    directories: int = 0
    hidden: int = 0
    unreadable: int = 0
    errors: list[str] = field(default_factory=list)
