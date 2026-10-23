"""High-level engine shared by the CLI and the GUI.

Both front-ends call the same functions, so the graphical app never
re-implements file handling: preview, planning, execution, history and undo
behave identically no matter which interface started them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ezsort.classifier import classify_batch
from ezsort.config import (
    get_excluded_dirs,
    get_excluded_extensions,
    load_config,
)
from ezsort.constants import PARTIAL_DOWNLOAD_EXTENSIONS
from ezsort.duplicate import find_duplicates
from ezsort.history import (
    UndoReport,
    clear_history,
    get_batch,
    get_history,
    history_stats,
    record_operations,
    remove_batch,
    undo_batch,
    undo_batch_detailed,
    undo_last,
    undo_last_detailed,
)
from ezsort.models import FileItem, Operation, OperationResult
from ezsort.organizer import execute_operations
from ezsort.planner import PlanResult, create_plan_detailed
from ezsort.scanner import ScanResult, scan_directory_ex

logger = logging.getLogger(__name__)


@dataclass
class PreviewResult:
    """Everything the UI needs to show a preview of a planned sort."""

    folder: Path
    files: list[FileItem] = field(default_factory=list)
    operations: list[Operation] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    duplicates: int = 0
    total_size: int = 0

    @property
    def ready(self) -> int:
        return len(self.operations)


@dataclass
class ExecutionSummary:
    """Outcome of running a plan."""

    results: list[OperationResult] = field(default_factory=list)
    batch_id: str = ""
    dry_run: bool = False
    cancelled: bool = False
    elapsed: float = 0.0
    #: How many moves this run was asked to perform (after duplicate skips).
    planned: int = 0
    #: Planned moves that were deliberately not run (duplicate_strategy=skip).
    skipped_duplicates: list[Operation] = field(default_factory=list)

    @property
    def moved(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def failures(self) -> list[OperationResult]:
        return [r for r in self.results if not r.success]


def _file_filter(config: dict[str, Any]) -> Callable[[Path], Optional[str]]:
    """Return a predicate that yields a skip-reason (or None to keep)."""
    excluded_exts = {
        e.lower() for e in get_excluded_extensions(config)
    }
    partial_exts = {e.lower() for e in PARTIAL_DOWNLOAD_EXTENSIONS}
    skip_partial = bool(config.get("skip_partial_downloads", True))

    def check(path: Path) -> Optional[str]:
        ext = path.suffix.lower()
        if ext in excluded_exts:
            return f"Excluded extension {ext}"
        if skip_partial and ext in partial_exts:
            return f"Looks like an unfinished download ({ext})"
        return None

    return check


def scan_folder(
    folder: Path,
    config: dict[str, Any],
    recursive: bool = False,
) -> ScanResult:
    """Scan a folder honoring the user's configuration."""
    return scan_directory_ex(
        folder,
        recursive=recursive,
        excluded_dirs=get_excluded_dirs(config),
        skip_hidden=bool(config.get("skip_hidden", True)),
    )


def build_preview(
    folder: Path,
    config: dict[str, Any] | None = None,
    recursive: bool = False,
    count_duplicates: bool = False,
) -> PreviewResult:
    """Scan, classify and plan without touching a single file."""
    if config is None:
        config = load_config()

    result = scan_folder(folder, config, recursive=recursive)
    preview = PreviewResult(folder=folder, errors=list(result.errors))

    should_skip = _file_filter(config)
    for item in result.files:
        reason = should_skip(item.path)
        if reason:
            preview.skipped.append((item.path, reason))
            continue
        preview.files.append(item)
        try:
            preview.total_size += item.size
        except Exception:  # pragma: no cover
            pass

    classified = classify_batch(preview.files, config)
    for _item, category, _reason in classified:
        top = category.split("/")[0]
        preview.categories[top] = preview.categories.get(top, 0) + 1

    plan: PlanResult = create_plan_detailed(classified, folder)
    preview.operations = plan.operations
    preview.skipped.extend(plan.skipped)

    if count_duplicates:
        try:
            dupes = find_duplicates([i.path for i in preview.files])
            preview.duplicates = sum(len(p) - 1 for p in dupes.values())
        except OSError as e:  # pragma: no cover
            preview.errors.append(f"Duplicate check failed: {e}")

    return preview


def run_plan(
    preview: PreviewResult | list[Operation],
    dry_run: bool = False,
    progress: Optional[Callable[[int, int, Operation], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    record: bool = True,
    config: dict[str, Any] | None = None,
) -> ExecutionSummary:
    """Execute a preview/plan, record history, and summarize the outcome.

    When ``config["duplicate_strategy"] == "skip"`` and the user's config
    says so, planned moves whose destination name is already taken are not
    executed at all (instead of being stored under a `` (n)`` name).
    """
    import time as _time

    if isinstance(preview, PreviewResult):
        planned = list(preview.operations)
    else:
        planned = list(preview)

    summary = ExecutionSummary(dry_run=dry_run)

    if config is not None and str(config.get("duplicate_strategy", "rename")) == "skip":
        runnable: list[Operation] = []
        for op in planned:
            if op.collision:
                summary.skipped_duplicates.append(op)
            else:
                runnable.append(op)
        planned = runnable

    summary.planned = len(planned)
    start = _time.perf_counter()
    results = execute_operations(
        planned,
        dry_run=dry_run,
        progress=progress,
        cancel_check=cancel_check,
    )
    elapsed = _time.perf_counter() - start

    summary.results = results
    summary.elapsed = elapsed
    summary.cancelled = (
        cancel_check is not None and len(results) < len(planned)
    )

    if record and not dry_run and results:
        try:
            folder = preview.folder if isinstance(preview, PreviewResult) else None
            summary.batch_id = record_operations(
                results,
                folder=str(folder) if folder else None,
                cancelled=summary.cancelled,
                planned_total=summary.planned,
            )
        except Exception:  # pragma: no cover - never lose the run itself
            logger.warning("Could not record history", exc_info=True)

    return summary


def organize_folder(
    folder: Path,
    config: dict[str, Any] | None = None,
    recursive: bool = False,
    dry_run: bool = True,
    progress: Optional[Callable[[int, int, Operation], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    count_duplicates: bool = False,
) -> tuple[PreviewResult, ExecutionSummary]:
    """Convenience wrapper: preview, then (optionally) execute."""
    preview = build_preview(
        folder,
        config=config,
        recursive=recursive,
        count_duplicates=count_duplicates,
    )
    summary = run_plan(
        preview,
        dry_run=dry_run,
        progress=progress,
        cancel_check=cancel_check,
        config=config,
    )
    return preview, summary


# ---------------------------------------------------------------------------
# History helpers (thin wrappers so front-ends import from one place)
# ---------------------------------------------------------------------------

def load_history() -> list[dict[str, Any]]:
    return get_history()


def load_batch(batch_id: str) -> dict[str, Any] | None:
    return get_batch(batch_id)


def undo_last_batch() -> tuple[bool, str]:
    return undo_last()


def undo_specific_batch(batch_id: str) -> tuple[bool, str]:
    return undo_batch(batch_id)


def undo_last_report() -> UndoReport:
    """Undo the newest batch and return the structured report (GUI)."""
    return undo_last_detailed()


def undo_specific_report(batch_id: str) -> UndoReport:
    """Undo a batch and return the structured report (GUI)."""
    return undo_batch_detailed(batch_id)


def wipe_history() -> None:
    clear_history()


def drop_batch(batch_id: str) -> bool:
    return remove_batch(batch_id)


def stats() -> dict[str, Any]:
    return history_stats()
