"""Background task execution that keeps the Tk main loop responsive.

Every blocking operation (scanning, moving files, undo, watching) runs on a
worker thread. Results and progress events travel through a Queue that is
drained on the Tk thread, so widgets are only ever touched from the UI
thread.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TaskRunner:
    """Runs functions on worker threads and marshals callbacks to Tk."""

    def __init__(self, root) -> None:
        self._root = root
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._running = 0
        self._closed = False
        self._poll()

    # -- public API --------------------------------------------------------

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_done: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[BaseException], None]] = None,
        **kwargs: Any,
    ) -> None:
        """Run ``fn(*args, **kwargs)`` on a thread; callbacks fire on the Tk thread."""
        self._running += 1

        def worker() -> None:
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 - delivered to the UI
                logger.exception("Background task failed")
                self._put(("error", on_error, exc))
            else:
                self._put(("done", on_done, result))

        thread = threading.Thread(target=worker, daemon=True, name="ezsort-worker")
        thread.start()

    def emitter(self, callback: Callable[[dict], None]) -> Callable[[dict], None]:
        """Return a thread-safe function that delivers event dicts to Tk."""

        def emit(payload: dict) -> None:
            self._put(("event", callback, payload))

        return emit

    @property
    def busy(self) -> bool:
        return self._running > 0

    def close(self) -> None:
        self._closed = True

    # -- internals ---------------------------------------------------------

    def _put(self, item: tuple) -> None:
        if self._closed:
            return
        self._queue.put(item)

    def _poll(self) -> None:
        if self._closed:
            return
        # Drain without starving the event loop if tasks flood the queue.
        for _ in range(50):
            try:
                kind, callback, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if callback is None:
                if kind in ("done", "error"):
                    self._running = max(0, self._running - 1)
                continue
            try:
                callback(payload)
            except Exception:  # pragma: no cover - UI callback bug
                logger.exception("UI callback raised")
            finally:
                if kind in ("done", "error"):
                    self._running = max(0, self._running - 1)
        try:
            self._root.after(60, self._poll)
        except Exception:  # root destroyed while draining
            self._closed = True


class CancelToken:
    """Cooperative cancellation flag shared with the engine."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> bool:
        return self._event.is_set()


def new_task_runner(root) -> TaskRunner:
    return TaskRunner(root)
