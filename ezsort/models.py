"""Data models for EzSort operations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FileItem:
    """Represents a discovered file."""

    path: Path
    size: int = 0
    extension: str = ""
    is_symlink: bool = False
    is_dir: bool = False

    def __post_init__(self) -> None:
        if not self.extension and self.path.is_file():
            self.extension = self.path.suffix.lower()
        if self.size == 0 and self.path.is_file():
            try:
                self.size = self.path.stat().st_size
            except OSError:
                self.size = 0
        self.is_symlink = self.path.is_symlink()
        self.is_dir = self.path.is_dir()


@dataclass
class Operation:
    """Represents a single file operation (move)."""

    source: Path
    destination: Path
    category: str
    reason: str
    operation_id: str = ""

    def __post_init__(self) -> None:
        if not self.operation_id:
            self.operation_id = hashlib.sha256(
                str(self.source).encode()
            ).hexdigest()[:12]


@dataclass
class OperationResult:
    """Result of executing an operation."""

    operation: Operation
    success: bool
    error: Optional[str] = None
    timestamp: str = ""


@dataclass
class ScanReport:
    """Results of scanning a directory."""

    total_files: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    duplicates: int = 0
    organizable: int = 0
    symlinks: int = 0
    directories: int = 0
