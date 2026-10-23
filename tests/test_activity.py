"""Persistent activity log: compatibility, trimming and corruption safety."""

from __future__ import annotations

import json

import pytest

from ezsort import activity


@pytest.fixture
def activity_file(tmp_path, monkeypatch):
    path = tmp_path / "activity.json"
    monkeypatch.setattr(activity, "get_activity_path", lambda: path)
    return path


def test_entries_round_trip(activity_file):
    activity.append_activity(
        {"time": "10:00:00", "type": "moved", "message": "Moved 3 files"}
    )
    activity.append_activity(
        {"time": "10:00:01", "type": "info", "message": "Watch mode idle"}
    )
    entries = activity.load_activity()
    assert [e["message"] for e in entries] == [
        "Moved 3 files", "Watch mode idle",
    ]
    assert entries[0]["type"] == "moved"


def test_old_entries_without_type_still_load(activity_file):
    """v0.3.0 only ever wrote ``time`` and ``message`` for some events."""
    activity_file.write_text(
        json.dumps([{"time": "09:00", "message": "legacy entry"}]),
        encoding="utf-8",
    )
    assert activity.load_activity() == [
        {"time": "09:00", "message": "legacy entry"}
    ]


def test_save_caps_the_log_at_max_entries(activity_file):
    entries = [
        {"time": f"10:{i:02d}", "type": "info", "message": f"entry {i}"}
        for i in range(activity.MAX_ENTRIES + 75)
    ]
    activity.save_activity(entries)
    loaded = activity.load_activity()
    assert len(loaded) == activity.MAX_ENTRIES
    assert loaded[0]["message"] == "entry 75", "the oldest entries are trimmed"
    assert loaded[-1]["message"] == f"entry {activity.MAX_ENTRIES + 74}"

    activity.append_activity(
        {"time": "11:00", "type": "info", "message": "newest"}
    )
    assert len(activity.load_activity()) == activity.MAX_ENTRIES
    assert activity.load_activity()[-1]["message"] == "newest"


def test_corrupt_file_is_moved_aside(activity_file):
    activity_file.write_text("{not valid json", encoding="utf-8")
    assert activity.load_activity() == []
    assert not activity_file.exists()
    backup = activity_file.with_name("activity.json.corrupt")
    assert backup.is_file(), "the unreadable log must be kept for inspection"


def test_non_list_root_is_treated_as_corrupt(activity_file):
    activity_file.write_text('{"time": "10:00"}', encoding="utf-8")
    assert activity.load_activity() == []
    assert activity_file.with_name("activity.json.corrupt").is_file()


def test_non_dict_entries_are_ignored(activity_file):
    activity_file.write_text(
        json.dumps([1, "nope", {"time": "10:00", "message": "ok"}]),
        encoding="utf-8",
    )
    assert activity.load_activity() == [{"time": "10:00", "message": "ok"}]


def test_clear_activity_empties_the_log(activity_file):
    activity.append_activity({"time": "10:00", "type": "info", "message": "x"})
    activity.clear_activity()
    assert activity.load_activity() == []
