"""Tests for the file scanner module."""

import pytest
from pathlib import Path
from ezsort.scanner import scan_directory, scan_for_report


@pytest.fixture
def scan_dir(tmp_path):
    """Create a test directory structure."""
    (tmp_path / "file1.txt").write_text("hello")
    (tmp_path / "file2.jpg").write_text("image")
    (tmp_path / "file3.py").write_text("code")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested")
    return tmp_path


def test_scan_finds_files(scan_dir):
    files = scan_directory(scan_dir)
    assert len(files) == 3  # top-level files only


def test_scan_excludes_directories(scan_dir):
    files = scan_directory(scan_dir)
    for f in files:
        assert f.path.is_file()


def test_scan_recursive(scan_dir):
    files = scan_directory(scan_dir, recursive=True)
    assert len(files) == 4  # includes nested.txt


def test_scan_nonexistent_directory():
    files = scan_directory(Path("/nonexistent/path"))
    assert files == []


def test_scan_excludes_hidden_files(tmp_path):
    (tmp_path / ".hidden").write_text("hidden")
    (tmp_path / "visible.txt").write_text("visible")
    files = scan_directory(tmp_path)
    assert len(files) == 1
    assert files[0].path.name == "visible.txt"


def test_scan_excludes_named_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "normal_file.txt").write_text("file")
    files = scan_directory(tmp_path)
    assert len(files) == 1


def test_scan_report(scan_dir):
    report = scan_for_report(scan_dir)
    assert report.total_files == 3
    assert report.directories >= 1


def test_scan_empty_directory(tmp_path):
    files = scan_directory(tmp_path)
    assert files == []


def test_scan_symlinks(tmp_path):
    target = tmp_path / "real.txt"
    target.write_text("real")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
        files = scan_directory(tmp_path)
        # Symlinks should be skipped from file list
        file_names = [f.path.name for f in files]
        assert "real.txt" in file_names
    except OSError:
        pytest.skip("Symlinks not supported on this platform")
