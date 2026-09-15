"""Tests for duplicate detection."""

import pytest
from pathlib import Path
from ezsort.duplicate import compute_hash, find_duplicates, get_duplicate_report


def test_compute_hash(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h = compute_hash(f)
    assert len(h) == 64  # SHA-256 hex digest length


def test_same_content_same_hash(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    content = "identical content"
    f1.write_text(content)
    f2.write_text(content)
    assert compute_hash(f1) == compute_hash(f2)


def test_different_content_different_hash(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("content A")
    f2.write_text("content B")
    assert compute_hash(f1) != compute_hash(f2)


def test_find_duplicates(tmp_path):
    f1 = tmp_path / "copy1.txt"
    f2 = tmp_path / "copy2.txt"
    f3 = tmp_path / "unique.txt"
    content = "duplicate content"
    f1.write_text(content)
    f2.write_text(content)
    f3.write_text("something else")
    
    dupes = find_duplicates([f1, f2, f3])
    assert len(dupes) == 1
    assert len(list(dupes.values())[0]) == 2


def test_no_duplicates(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("content 1")
    f2.write_text("content 2")
    dupes = find_duplicates([f1, f2])
    assert len(dupes) == 0


def test_get_duplicate_report(tmp_path):
    f1 = tmp_path / "copy1.txt"
    f2 = tmp_path / "copy2.txt"
    content = "duplicate"
    f1.write_text(content)
    f2.write_text(content)
    
    report = get_duplicate_report([f1, f2])
    assert len(report) == 1
    assert report[0]["count"] == 2


def test_empty_file_list():
    dupes = find_duplicates([])
    assert len(dupes) == 0
