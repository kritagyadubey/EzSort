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


def _wait_for(predicate, timeout: float = 60.0) -> bool:
    """Poll ``predicate`` until true or ``timeout``. Never raises.

    Deliberately non-raising: every test here stops the watcher and joins it
    *before* judging the result. That matters on CI, where antivirus can hold
    a rename or a history write for tens of seconds - the work is still
    correct, just slow - and because a watcher thread left running after
    ``join`` would flush its history into the *next* test's ``EZSORT_HOME``.
    The budget is generous on purpose: it is only ever spent when something
    is already wrong, and the healthy path returns the moment it succeeds.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def _stopped(events: list[dict]) -> bool:
    """True once the watcher has flushed and announced it is winding down.

    The watcher emits this message only *after* ``flush_history()`` has
    written the batch, and it is the last thing the function does. Waiting on
    it - rather than on thread liveness - absorbs the stalls a runner's
    antivirus puts on those writes, while still proving the history record
    exists and the thread is about to exit.
    """
    return any("stopped" in str(e.get("message", "")).lower() for e in events)


def test_watch_moves_new_stable_file(tmp_path):
    folder = tmp_path / "watched"
    folder.mkdir()
    thread, stop, events = _run_watch(folder)
    target = folder / "Documents" / "arrived.pdf"
    try:
        time.sleep(1.4)  # let it settle with only pre-existing content
        (folder / "arrived.pdf").write_bytes(b"pdf")
        _wait_for(lambda: target.exists())
    finally:
        stop.set()
        thread.join(timeout=30)

    # Judge only after the watcher has fully wound down: "stopped" is emitted
    # *after* the history flush and is the last thing the function does, so by
    # the time it arrives every move and history write has finished. That flush
    # is the file write a CI runner's antivirus stalls (observed: thread still
    # alive 30s after stop, with no "Recorded batch" line yet).
    assert _wait_for(lambda: _stopped(events)), (
        f"watcher never finished stopping; "
        f"events={[e.get('message') for e in events]}"
    )
    thread.join(timeout=10)
    assert not thread.is_alive()

    assert target.exists(), (
        f"watch did not move the file; events={[e.get('message') for e in events]}"
    )


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
        thread.join(timeout=30)


def test_watch_records_history(tmp_path):
    folder = tmp_path / "watched"
    folder.mkdir()
    thread, stop, events = _run_watch(folder)
    target = folder / "Music" / "new-song.mp3"
    try:
        time.sleep(1.2)
        (folder / "new-song.mp3").write_bytes(b"mp3")
        _wait_for(lambda: target.exists())
    finally:
        stop.set()
        # Joining before judging is what keeps a merely-slow move (and the
        # thread performing it) inside *this* test: a short join used to let
        # the thread survive into the next test and record its batch there.
        thread.join(timeout=30)

    assert _wait_for(lambda: _stopped(events)), (
        f"watcher never finished stopping; "
        f"events={[e.get('message') for e in events]}"
    )
    thread.join(timeout=10)
    assert not thread.is_alive()

    # Everything above ran after the watcher quiesced, so these outcomes are
    # read from a finished system: the move happened, and the batch is on disk
    # in *this* test's EZSORT_HOME.
    assert target.exists(), (
        f"watch did not move the file; events={[e.get('message') for e in events]}"
    )
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
        thread.join(timeout=30)


def test_watch_event_callback_receives_messages(tmp_path):
    folder = tmp_path / "watched"
    folder.mkdir()
    received: list[dict] = []
    thread, stop, _ = _run_watch(folder, on_event=received.append)
    target = folder / "Documents" / "notes.txt"
    try:
        time.sleep(1.2)
        (folder / "notes.txt").write_bytes(b"txt")
        _wait_for(lambda: target.exists())
    finally:
        stop.set()
        thread.join(timeout=30)

    # See test_watch_records_history: wait for the watcher's own post-flush
    # "stopped" announcement before judging anything, so a merely-slow move or
    # history write is not mistaken for a failure.
    assert _wait_for(lambda: _stopped(received)), (
        f"watcher never finished stopping; "
        f"events={[e.get('message') for e in received]}"
    )
    thread.join(timeout=10)
    assert not thread.is_alive()

    assert target.exists(), (
        f"watch did not move the file; events={[e.get('message') for e in received]}"
    )

    kinds = [e.get("type") for e in received]
    assert "info" in kinds
    assert "detected" in kinds
    assert "moved" in kinds
