"""Tests for the organizer module."""

import pytest
from pathlib import Path
from ezsort.organizer import execute_operations, execute_single
from ezsort.models import Operation


@pytest.fixture
def organize_dir(tmp_path):
    """Create a test directory for organizing."""
    src = tmp_path / "source"
    src.mkdir()
    (src / "photo.jpg").write_text("image data")
    (src / "doc.pdf").write_text("doc data")
    return src


def test_execute_dry_run(organize_dir):
    op = Operation(
        source=organize_dir / "photo.jpg",
        destination=organize_dir / "Images" / "photo.jpg",
        category="Images",
        reason="test",
    )
    result = execute_single(op, dry_run=True)
    assert result.success
    # File should NOT be moved
    assert (organize_dir / "photo.jpg").exists()
    assert not (organize_dir / "Images" / "photo.jpg").exists()


def test_execute_real_move(organize_dir):
    op = Operation(
        source=organize_dir / "photo.jpg",
        destination=organize_dir / "Images" / "photo.jpg",
        category="Images",
        reason="test",
    )
    result = execute_single(op, dry_run=False)
    assert result.success
    assert (organize_dir / "Images" / "photo.jpg").exists()
    assert not (organize_dir / "photo.jpg").exists()


def test_execute_creates_directory(organize_dir):
    op = Operation(
        source=organize_dir / "doc.pdf",
        destination=organize_dir / "Documents" / "doc.pdf",
        category="Documents",
        reason="test",
    )
    result = execute_single(op, dry_run=False)
    assert result.success
    assert (organize_dir / "Documents").is_dir()


def test_execute_no_overwrite(organize_dir):
    # Create a file at destination
    dest_dir = organize_dir / "Images"
    dest_dir.mkdir()
    (dest_dir / "photo.jpg").write_text("existing")
    
    op = Operation(
        source=organize_dir / "photo.jpg",
        destination=dest_dir / "photo.jpg",
        category="Images",
        reason="test",
    )
    result = execute_single(op, dry_run=False)
    assert result.success
    # Original should exist with renamed name
    assert (dest_dir / "photo (1).jpg").exists()


def test_execute_batch(organize_dir):
    ops = [
        Operation(
            source=organize_dir / "photo.jpg",
            destination=organize_dir / "Images" / "photo.jpg",
            category="Images",
            reason="test",
        ),
        Operation(
            source=organize_dir / "doc.pdf",
            destination=organize_dir / "Documents" / "doc.pdf",
            category="Documents",
            reason="test",
        ),
    ]
    results = execute_operations(ops, dry_run=False)
    assert len(results) == 2
    assert all(r.success for r in results)
    assert (organize_dir / "Images" / "photo.jpg").exists()
    assert (organize_dir / "Documents" / "doc.pdf").exists()


def test_execute_nonexistent_source(organize_dir):
    op = Operation(
        source=organize_dir / "nonexistent.txt",
        destination=organize_dir / "Documents" / "nonexistent.txt",
        category="Documents",
        reason="test",
    )
    result = execute_single(op, dry_run=False)
    assert not result.success
    assert result.error is not None
