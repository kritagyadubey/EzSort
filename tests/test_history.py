"""Tests for history and undo."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch
from ezsort.history import record_operations, undo_last, get_history, clear_history
from ezsort.models import Operation, OperationResult


@pytest.fixture(autouse=True)
def isolation(tmp_path, monkeypatch):
    """Isolate history operations to a temp directory."""
    hist_path = tmp_path / "history.json"
    monkeypatch.setattr("ezsort.history.get_history_path", lambda: hist_path)
    return hist_path


def make_result(source: Path, dest: Path, success: bool = True):
    op = Operation(
        source=source,
        destination=dest,
        category="Documents",
        reason="test",
    )
    return OperationResult(operation=op, success=success, timestamp="2026-01-01T00:00:00")


def test_record_operations(tmp_path):
    src = tmp_path / "file.txt"
    src.write_text("content")
    dest = tmp_path / "Documents" / "file.txt"
    dest.parent.mkdir()
    
    result = make_result(src, dest)
    batch_id = record_operations([result])
    assert batch_id == "001"
    
    history = get_history()
    assert len(history) == 1
    assert history[0]["total_moved"] == 1


def test_undo_last(tmp_path):
    src = tmp_path / "file.txt"
    dest = tmp_path / "Documents" / "file.txt"
    dest.parent.mkdir()
    dest.write_text("content")
    
    result = make_result(src, dest)
    record_operations([result])
    
    success, msg = undo_last()
    assert success
    assert src.exists()
    assert not dest.exists()


def test_undo_empty_history():
    success, msg = undo_last()
    assert not success
    assert "No operations" in msg


def test_clear_history(tmp_path):
    src = tmp_path / "file.txt"
    dest = tmp_path / "Documents" / "file.txt"
    dest.parent.mkdir()
    dest.write_text("content")
    
    result = make_result(src, dest)
    record_operations([result])
    
    clear_history()
    assert get_history() == []


def test_undo_missing_file(tmp_path):
    src = tmp_path / "file.txt"
    dest = tmp_path / "Documents" / "file.txt"
    dest.parent.mkdir()
    # Don't create the dest file - simulate it was already moved/deleted
    
    result = make_result(src, dest)
    record_operations([result])
    
    success, msg = undo_last()
    assert success  # Still succeeds, just reports missing file
    assert "error" in msg.lower() or "Restored" in msg


def test_multiple_operations_undo(tmp_path):
    files = []
    for i in range(3):
        src = tmp_path / f"file{i}.txt"
        src.write_text(f"content {i}")
        dest = tmp_path / "Docs" / f"file{i}.txt"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(f"content {i}")
        files.append((src, dest))
    
    results = [make_result(s, d) for s, d in files]
    record_operations(results)
    
    success, msg = undo_last()
    assert success
    for src, _ in files:
        assert src.exists()
