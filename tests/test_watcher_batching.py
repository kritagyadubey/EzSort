"""Watch-mode batching and quiet-mode behaviour.

Watch mode records one history batch per *wave* of downloads rather than
one batch (and one full history rewrite) per moved file.
"""

from __future__ import annotations

import io
import threading
import time
from contextlib import redirect_stdout
from pathlib import Path

from ezsort.config import load_config
from ezsort.history import get_history
from ezsort.watcher import watch_directory


def _run_watch(folder, *, interval: int = 1, config=None, on_event=None,
               record_history: bool = True, echo: bool = False):
    """Run watch_directory in a thread until the returned stop event is set."""
    stop = threading.Event()
    events: list[dict] = []
    thread = threading.Thread(
        target=watch_directory,
        kwargs=dict(
            directory=folder,
            interval=interval,
            recursive=False,
            config=config if config is not None else load_config(),
            on_event=on_event or events.append,
            stop_event=stop,
            record_history=record_history,
            echo=echo,
        ),
        daemon=True,
    )
    thread.start()
    return thread, stop, events


def _wait_until(predicate, timeout: float = 8.0, label: str = "condition") -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.15)
    raise AssertionError(f"timed out waiting for {label}")


def test_watch_batches_one_wave_into_one_history(tmp_path):
    """A burst of new files lands as a single undoable history batch."""
    folder = tmp_path / "watched"
    folder.mkdir()
    thread, stop, events = _run_watch(folder)
    try:
        time.sleep(1.4)  # let the watcher settle on the empty folder
        for name in ("a.pdf", "b.mp3", "c.jpg"):
            (folder / name).write_bytes(b"data")

        _wait_until(
            lambda: (folder / "Documents" / "a.pdf").exists()
            and (folder / "Music" / "b.mp3").exists()
            and (folder / "Images" / "c.jpg").exists(),
            label="all three files moved",
        )
    finally:
        stop.set()
        thread.join(timeout=8)
    assert not thread.is_alive()

    # The quiet poll after the burst flushes the wave as one batch, so
    # undo reverses the whole burst at once.
    history = get_history()
    assert len(history) == 1, (
        f"expected one batch for one wave, got {len(history)}: "
        f"{[b['total_moved'] for b in history]}"
    )
    assert history[0]["total_moved"] == 3
    sources = {Path(op["source"]).name for op in history[0]["operations"]}
    assert sources == {"a.pdf", "b.mp3", "c.jpg"}


def test_watch_separate_waves_create_separate_batches(tmp_path):
    """Two waves separated by a quiet poll undo independently."""
    folder = tmp_path / "watched"
    folder.mkdir()
    thread, stop, _ = _run_watch(folder)
    try:
        time.sleep(1.4)
        (folder / "first.pdf").write_bytes(b"1")
        _wait_until(lambda: (folder / "Documents" / "first.pdf").exists(),
                    label="first wave moved")
        time.sleep(2.5)  # several quiet polls -> first batch flushed

        (folder / "second.pdf").write_bytes(b"2")
        _wait_until(lambda: (folder / "Documents" / "second.pdf").exists(),
                    label="second wave moved")
    finally:
        stop.set()
        thread.join(timeout=8)

    history = get_history()
    assert len(history) == 2, f"expected two batches, got {len(history)}"
    assert history[0]["total_moved"] == 1
    assert history[1]["total_moved"] == 1


def test_watch_echo_false_prints_nothing(tmp_path):
    """echo=False keeps stdout clean (the windowed GUI EXE has no console)."""
    folder = tmp_path / "watched"
    folder.mkdir()
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        thread, stop, _ = _run_watch(folder, echo=False)
        try:
            time.sleep(1.4)
            (folder / "quiet.pdf").write_bytes(b"pdf")
            _wait_until(lambda: (folder / "Documents" / "quiet.pdf").exists(),
                        label="file moved while quiet")
        finally:
            stop.set()
            thread.join(timeout=8)
    assert buffer.getvalue() == "", (
        f"echo=False still wrote to stdout: {buffer.getvalue()!r}"
    )


def test_watch_echo_true_still_prints(tmp_path):
    """The CLI keeps its banner + per-move output."""
    folder = tmp_path / "watched"
    folder.mkdir()
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        thread, stop, _ = _run_watch(folder, echo=True)
        try:
            time.sleep(1.4)
            (folder / "loud.pdf").write_bytes(b"pdf")
            _wait_until(lambda: (folder / "Documents" / "loud.pdf").exists(),
                        label="file moved while echoing")
        finally:
            stop.set()
            thread.join(timeout=8)
    out = buffer.getvalue()
    assert "EzSort Watch Mode" in out
    assert "loud.pdf" in out


def test_watch_flushes_pending_history_on_stop(tmp_path):
    """Stopping mid-wave still records the moves (nothing is lost)."""
    folder = tmp_path / "watched"
    folder.mkdir()
    thread, stop, _ = _run_watch(folder)
    try:
        time.sleep(1.4)
        (folder / "late.pdf").write_bytes(b"pdf")
        _wait_until(lambda: (folder / "Documents" / "late.pdf").exists(),
                    label="file moved")
        # Stop immediately: the quiet-poll flush may not have happened yet,
        # but the exit flush must still record the batch.
        stop.set()
        thread.join(timeout=8)
    finally:
        stop.set()
        thread.join(timeout=8)

    history = get_history()
    assert history, "moves were lost when watch mode stopped"
    assert history[-1]["total_moved"] >= 1
