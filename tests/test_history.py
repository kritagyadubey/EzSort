"""Tests for history and undo."""

import pytest
from pathlib import Path
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
    # Realistic post-sort state: the originals are gone, copies live in Docs/
    files = []
    for i in range(3):
        src = tmp_path / f"file{i}.txt"
        dest = tmp_path / "Docs" / f"file{i}.txt"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(f"content {i}")
        files.append((src, dest))

    results = [make_result(s, d) for s, d in files]
    record_operations(results)

    success, msg = undo_last()
    assert success
    for src, dest in files:
        assert src.exists()
        assert not dest.exists()


def test_undo_never_overwrites_existing_file(tmp_path):
    # If something already occupies the original location, undo must NOT
    # destroy it: it reports a conflict and keeps the record for a retry.
    src = tmp_path / "file.txt"
    src.write_text("NEW content that must survive")
    dest = tmp_path / "Documents" / "file.txt"
    dest.parent.mkdir()
    dest.write_text("organized content")

    record_operations([make_result(src, dest)])

    success, msg = undo_last()
    assert not success
    assert "occupied" in msg or "conflict" in msg.lower()
    # Nothing was destroyed
    assert src.read_text() == "NEW content that must survive"
    assert dest.read_text() == "organized content"
    # The failed undo stays in history so it can be retried
    assert len(get_history()) == 1


def test_undo_partial_failure_keeps_remaining_records(tmp_path):
    # One file can be restored, one is blocked by a conflict.
    ok_src = tmp_path / "ok.txt"
    ok_dest = tmp_path / "Docs" / "ok.txt"
    ok_dest.parent.mkdir()
    ok_dest.write_text("ok")

    blocked_src = tmp_path / "blocked.txt"
    blocked_src.write_text("occupier")
    blocked_dest = tmp_path / "Docs" / "blocked.txt"
    blocked_dest.write_text("blocked")

    record_operations([make_result(ok_src, ok_dest), make_result(blocked_src, blocked_dest)])

    success, msg = undo_last()
    assert not success
    assert ok_src.exists()          # restored
    assert blocked_dest.exists()    # not moved
    history = get_history()
    assert len(history) == 1
    assert len(history[0]["operations"]) == 1  # only the blocked one remains


def test_batch_ids_stay_unique_after_removal(tmp_path):
    ids = []
    for _ in range(3):
        src = tmp_path / f"a{_}.txt"
        dest = tmp_path / "D" / f"a{_}.txt"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text("x")
        ids.append(record_operations([make_result(src, dest)]))
    assert ids == ["001", "002", "003"]

    from ezsort.history import remove_batch
    assert remove_batch("002")

    src = tmp_path / "next.txt"
    dest = tmp_path / "D" / "next.txt"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text("x")
    record_operations([make_result(src, dest)])

    all_ids = [b["batch_id"] for b in get_history()]
    assert len(all_ids) == len(set(all_ids)), f"duplicate batch ids: {all_ids}"
