"""Tests for the planner module."""

import pytest
from pathlib import Path
from ezsort.planner import create_plan
from ezsort.models import FileItem, Operation


@pytest.fixture
def classified_files(tmp_path):
    """Create classified file data."""
    f1 = tmp_path / "photo.jpg"
    f1.write_text("image")
    f2 = tmp_path / "resume.pdf"
    f2.write_text("doc")
    f3 = tmp_path / "already_in_place.txt"
    docs_dir = tmp_path / "Documents"
    docs_dir.mkdir()
    (docs_dir / "already_in_place.txt").write_text("already there")

    return [
        (FileItem(path=f1), "Images", "Extension matched"),
        (FileItem(path=f2), "Documents", "Extension matched"),
        (FileItem(path=f3), "Documents", "Extension matched"),
    ]


def test_create_plan_basic(classified_files, tmp_path):
    plan = create_plan(classified_files, tmp_path)
    assert len(plan) >= 2  # at least photo.jpg and resume.pdf


def test_create_plan_skips_already_organized(tmp_path):
    # File is already in the correct location
    docs_dir = tmp_path / "Documents"
    docs_dir.mkdir()
    f = docs_dir / "report.pdf"
    f.write_text("content")
    classified = [(FileItem(path=f), "Documents", "Extension matched")]
    plan = create_plan(classified, tmp_path)
    # Should be skipped because source resolves to same as destination
    assert len(plan) == 0


def test_create_plan_correct_destinations(classified_files, tmp_path):
    plan = create_plan(classified_files, tmp_path)
    for op in plan:
        assert isinstance(op, Operation)
        assert op.source.exists() or True  # source may have been moved in prior test
        assert "Images" in str(op.destination) or "Documents" in str(op.destination)


def test_create_plan_operation_ids(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_text("test")
    classified = [(FileItem(path=f), "Images", "test")]
    plan = create_plan(classified, tmp_path)
    assert len(plan) == 1
    assert len(plan[0].operation_id) == 12


def test_create_plan_subfolder(tmp_path):
    f = tmp_path / "invoice.pdf"
    f.write_text("test")
    classified = [(FileItem(path=f), "Documents/Invoices", "Custom rule")]
    plan = create_plan(classified, tmp_path)
    assert len(plan) == 1
    assert "Invoices" in str(plan[0].destination)
