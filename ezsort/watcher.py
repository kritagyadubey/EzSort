"""Watch mode - monitors a directory for new files."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from ezsort.classifier import classify_file
from ezsort.config import get_excluded_dirs, get_excluded_extensions
from ezsort.constants import PARTIAL_DOWNLOAD_EXTENSIONS
from ezsort.history import record_operations
from ezsort.models import FileItem
from ezsort.organizer import execute_operations
from ezsort.planner import create_plan
from ezsort.scanner import scan_directory_ex
from ezsort.utils import is_hidden, path_exists

logger = logging.getLogger(__name__)

#: Event callback: receives a dict with at least ``type`` in
#: {"detected", "moved", "skipped", "failed", "error", "info"}.
EventCallback = Callable[[dict], None]


def _emit(callback: Optional[EventCallback], payload: dict) -> None:
    if callback is None:
        return
    try:
        callback(payload)
    except Exception:  # pragma: no cover - user callbacks must not kill the loop
        logger.debug("Watch event callback raised", exc_info=True)


def watch_directory(
    directory: Path,
    interval: int = 2,
    recursive: bool = False,
    config: dict[str, Any] | None = None,
    on_move: Callable[[str], None] | None = None,
    on_event: Optional[EventCallback] = None,
    stop_event: Optional[threading.Event] = None,
    record_history: bool = True,
    echo: bool = True,
) -> None:
    """Watch a directory and organize new files as they appear.

    A file is only moved once its size and modification time have been
    stable across two consecutive polls, which prevents sorting away
    half-downloaded files.

    Args:
        directory: Directory to watch.
        interval: Seconds between scans.
        recursive: Whether to watch subdirectories.
        config: Optional configuration.
        on_move: Legacy callback invoked with a short message per move.
        on_event: Detailed callback receiving event dicts (GUI use).
        stop_event: Set this event to stop watching from another thread.
        record_history: Record moves to history so they can be undone.
        echo: Print banner/progress to stdout (CLI). The GUI passes False:
            writes to stdout are useless (and risky) in a windowed EXE.
    """
    interval = max(1, int(interval))
    stop = stop_event or threading.Event()

    _emit(on_event, {
        "type": "info",
        "message": f"Watching {directory} (every {interval}s)",
    })
    excluded_dirs = get_excluded_dirs(config)
    skip_hidden = bool((config or {}).get("skip_hidden", True))
    skip_partial = bool((config or {}).get("skip_partial_downloads", True))
    excluded_exts = set(get_excluded_extensions(config))
    # Excluded extensions are always skipped; partial-download extensions
    # (.part, .crdownload, ...) are skipped only when enabled in config.
    partial_exts = set(excluded_exts)
    if skip_partial:
        partial_exts |= {e.lower() for e in PARTIAL_DOWNLOAD_EXTENSIONS}
    if echo:
        print("\n  EzSort Watch Mode")
        print(f"  Watching: {directory}")
        print("  Press Ctrl+C to stop\n")

    # path -> (size, mtime) observed on the previous poll.
    previous: dict[Path, tuple[int, float]] = {}
    # Files confirmed stable and already handled (moved or skipped).
    handled: set[Path] = set()
    # Moves waiting to be written to history as one batch per "wave" of
    # downloads (instead of one history batch - and one full file rewrite -
    # per moved file).
    pending_results: list = []

    def flush_history() -> None:
        """Record every move accumulated since the last flush as one batch."""
        if not pending_results:
            return
        batch = pending_results[:]
        pending_results.clear()
        if record_history:
            try:
                batch_id = record_operations(batch, folder=str(directory))
                _emit(on_event, {
                    "type": "info",
                    "message": (
                        f"Recorded batch {batch_id}: "
                        f"{len(batch)} watched file(s) organized"
                    ),
                })
            except Exception:  # pragma: no cover - never lose the run itself
                logger.warning("Could not record watch-mode history", exc_info=True)

    def poll() -> int:
        """One scan pass. Returns how many files were handled this poll."""
        nonlocal previous
        result = scan_directory_ex(
            directory,
            recursive=recursive,
            excluded_dirs=excluded_dirs,
            skip_hidden=skip_hidden,
        )
        for err in result.errors:
            _emit(on_event, {"type": "error", "message": err})

        current: dict[Path, tuple[int, float]] = {}
        for item in result.files:
            try:
                stat = item.path.stat()
            except OSError:
                continue
            current[item.path] = (stat.st_size, stat.st_mtime)

        handled_now = 0
        # Detect new or changed files.
        for path, signature in current.items():
            if path in handled:
                continue
            if path not in previous:
                # First sighting: remember and wait for stability.
                _emit(on_event, {
                    "type": "detected",
                    "message": f"New file detected: {path.name}",
                    "path": str(path),
                })
                continue
            if previous[path] != signature:
                # Still being written - wait for the next poll.
                continue

            # Stable across two polls: safe to handle.
            handled.add(path)
            handled_now += 1
            results = _handle_stable_file(
                path=path,
                target_dir=directory,
                config=config,
                partial_exts=partial_exts,
                on_move=on_move,
                on_event=on_event,
                echo=echo,
            )
            pending_results.extend(results)

        # Forget files that disappeared (moved away or deleted) so a new
        # file reusing the same path is watched again.
        previous = {
            p: sig for p, sig in current.items() if p not in handled
        }
        handled.intersection_update(current)
        return handled_now

    # Prime with the initial contents: files that already exist are left
    # alone (use "Organize" for the existing mess; watch handles new files).
    try:
        initial = scan_directory_ex(
            directory,
            recursive=recursive,
            excluded_dirs=excluded_dirs,
            skip_hidden=skip_hidden,
        )
        for item in initial.files:
            handled.add(item.path)
    except OSError as e:
        logger.error("Cannot watch directory: %s", e)
        _emit(on_event, {"type": "error", "message": f"Cannot watch directory: {e}"})
        return

    try:
        while not stop.is_set():
            if stop.wait(timeout=interval):
                break
            try:
                moved_now = poll()
            except OSError as e:
                logger.error("Error scanning directory: %s", e)
                _emit(on_event, {"type": "error", "message": f"Scan error: {e}"})
                continue
            # A quiet poll after a productive one means the wave of
            # downloads has landed: record it as a single undoable batch.
            if pending_results and moved_now == 0:
                flush_history()
    except KeyboardInterrupt:
        print("\n  Watch mode stopped.")
        _emit(on_event, {"type": "info", "message": "Watch mode stopped."})
        flush_history()
        return

    flush_history()
    _emit(on_event, {"type": "info", "message": "Watch mode stopped."})


def _handle_stable_file(
    path: Path,
    target_dir: Path,
    config: dict[str, Any] | None,
    partial_exts: set[str],
    on_move: Callable[[str], None] | None,
    on_event: Optional[EventCallback],
    echo: bool = True,
) -> list:
    """Classify and move one file whose contents have stabilized.

    Returns the (possibly empty) list of OperationResults; history
    recording is the caller's job so related moves can be batched.
    """
    if not path_exists(path):
        return []

    if is_hidden(path) and (config or {}).get("skip_hidden", True):
        _emit(on_event, {
            "type": "skipped",
            "message": f"Skipped hidden file: {path.name}",
            "path": str(path),
        })
        return []

    if path.suffix.lower() in partial_exts:
        _emit(on_event, {
            "type": "skipped",
            "message": f"Skipped partial/temporary file: {path.name}",
            "path": str(path),
        })
        return []

    item = FileItem(path=path)
    category, reason = classify_file(item, config)
    plan = create_plan([(item, category, reason)], target_dir)

    if not plan:
        _emit(on_event, {
            "type": "skipped",
            "message": f"Already organized: {path.name}",
            "path": str(path),
        })
        return []

    results = execute_operations(plan, dry_run=False)

    if results and results[0].success:
        final = results[0].operation.destination
        message = f"Moved {path.name} -> {category}/"
        if echo:
            print(f"  Moved: {path.name} -> {final.parent.name}/")
        if on_move:
            on_move(message)
        _emit(on_event, {
            "type": "moved",
            "message": message,
            "path": str(path),
            "destination": str(final),
            "category": category,
        })
    else:
        error = results[0].error if results else "Unknown error"
        if echo:
            print(f"  Failed: {error}")
        _emit(on_event, {
            "type": "failed",
            "message": error or "Unknown error",
            "path": str(path),
        })
    return results
