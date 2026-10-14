"""Watch mode: stability checks, history recording, stop events."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from ezsort.config import load_config
from ezsort.history import get_history
from ezsort.watcher import watch_directory


def _run_watch(folder: Path, recursive: bool = False,
               config=None, on_event=None, record_history: bool = True):
    """Run watch_directory in a thread until the returned stop event is set."""
    stop = threading.Event()
    events: list[dict] = []
    collected = on_event or events.append

    thread = threading.Thread(
        target=watch_directory,
        kwargs=dict(
            directory=folder,
            interval=1,
            recursive=recursive,
            config=config if config is not None else load_config(),
            on_event=collected,
            stop_event=stop,
            record_history=record_history,
        ),
        daemon=True,
    )
    thread.start()
    return thread, stop, events


def test_watch_moves_new_stable_file(tmp_path):
    folder = tmp_path / "watched"
    folder.mkdir()
    thread, stop, events = _run_watch(folder)
    try:
        time.sleep(1.4)  # let it settle with only pre-existing content
        new_file = folder / "arrived.pdf"
        new_file.write_bytes(b"pdf")

        deadline = time.time() + 6
        while time.time() < deadline:
            if (folder / "Documents" / "arrived.pdf").exists():
                break
            time.sleep(0.2)
        assert (folder / "Documents" / "arrived.pdf").exists(), (
            f"watch did not move the file; events={[e.get('message') for e in events]}"
        )
    finally:
        stop.set()
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_watch_ignores_preexisting_files(tmp_path):
    folder = tmp_path / "watched"
    folder.mkdir()
    (folder / "old.pdf").write_bytes(b"old")

    thread, stop, events = _run_watch(folder)
    try:
        time.sleep(2.5)  # several polls
        assert (folder / "old.pdf").exists(), "pre-existing file was moved!"
        assert not (folder / "Documents").exists()
    finally:
        stop.set()
        thread.join(timeout=5)


def test_watch_records_history(tmp_path):
    folder = tmp_path / "watched"
    folder.mkdir()
    thread, stop, events = _run_watch(folder)
    try:
        time.sleep(1.2)
        (folder / "new-song.mp3").write_bytes(b"mp3")
        deadline = time.time() + 6
        while time.time() < deadline and not (folder / "Music").exists():
            time.sleep(0.2)
        assert (folder / "Music" / "new-song.mp3").exists()
    finally:
        stop.set()
        thread.join(timeout=5)

    history = get_history()
    assert history, "watch-mode move was not recorded in history"
    assert any(
        op["source"].endswith("new-song.mp3")
        for batch in history
        for op in batch["operations"]
    )


def test_watch_skips_partial_downloads(tmp_path):
    folder = tmp_path / "watched"
    folder.mkdir()
    thread, stop, events = _run_watch(folder)
    try:
        time.sleep(1.2)
        (folder / "bigfile.part").write_bytes(b"partial")
        time.sleep(2.5)  # enough polls to trigger if it were going to
        assert (folder / "bigfile.part").exists(), "partial download was moved!"
        assert not (folder / "Documents").exists()
    finally:
        stop.set()
        thread.join(timeout=5)


def test_watch_event_callback_receives_messages(tmp_path):
    folder = tmp_path / "watched"
    folder.mkdir()
    received: list[dict] = []
    thread, stop, _ = _run_watch(folder, on_event=received.append)
    try:
        time.sleep(1.2)
        (folder / "notes.txt").write_bytes(b"txt")
        deadline = time.time() + 6
        while time.time() < deadline and not (folder / "Documents").exists():
            time.sleep(0.2)
        assert (folder / "Documents" / "notes.txt").exists()
    finally:
        stop.set()
        thread.join(timeout=5)

    kinds = [e.get("type") for e in received]
    assert "info" in kinds
    assert "detected" in kinds
    assert "moved" in kinds
