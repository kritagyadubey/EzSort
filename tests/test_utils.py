"""Tests for utility functions."""

import pytest
from pathlib import Path
from ezsort.utils import get_unique_destination, format_size, is_within_directory


def test_get_unique_destination_no_conflict(tmp_path):
    dest = tmp_path / "file.txt"
    result = get_unique_destination(dest)
    assert result == dest


def test_get_unique_destination_conflict(tmp_path):
    dest = tmp_path / "file.txt"
    dest.write_text("existing")
    result = get_unique_destination(dest)
    assert result.name == "file (1).txt"
    assert result != dest


def test_get_unique_destination_multiple_conflicts(tmp_path):
    dest = tmp_path / "file.txt"
    dest.write_text("existing")
    (tmp_path / "file (1).txt").write_text("also exists")
    result = get_unique_destination(dest)
    assert result.name == "file (2).txt"


def test_get_unique_destination_preserves_extension(tmp_path):
    dest = tmp_path / "archive.tar.gz"
    dest.write_text("existing")
    result = get_unique_destination(dest)
    # Path.stem is "archive.tar" and suffix is ".gz" for double extensions
    assert result.name == "archive.tar (1).gz"


def test_format_size_bytes():
    assert format_size(0) == "0.0 B"
    assert format_size(500) == "500.0 B"


def test_format_size_kb():
    assert "KB" in format_size(1024)


def test_format_size_mb():
    assert "MB" in format_size(1024 * 1024)


def test_is_within_directory():
    base = Path("/home/user/docs")
    target = Path("/home/user/docs/file.txt")
    assert is_within_directory(base, target) is True


def test_is_not_within_directory():
    base = Path("/home/user/docs")
    target = Path("/home/user/other/file.txt")
    assert is_within_directory(base, target) is False
