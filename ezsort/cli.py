"""CLI entry point for EzSort."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from ezsort import __version__
from ezsort import engine
from ezsort.config import load_config
from ezsort.constants import BANNER, CATEGORY_ORDER, VERSION_STRING
from ezsort.utils import bold, get_unique_destination, green, red, yellow

ABOUT_TEXT = f"""
  {bold('EzSort')} v{__version__}
  Keep Your Files Sorted, Effortlessly.

  Made by Kritagya Dubey
  GitHub: https://github.com/kritagyadubey/EzSort
  License: MIT
"""


# ---------------------------------------------------------------------------
# Output helpers (honour --quiet)
# ---------------------------------------------------------------------------

_QUIET = False


def say(message: str = "") -> None:
    """Print normal output (suppressed by --quiet)."""
    if not _QUIET:
        print(message)


def warn(message: str) -> None:
    """Print a warning (suppressed by --quiet)."""
    if not _QUIET:
        print(yellow(message))


def err(message: str) -> None:
    """Print an error (always shown)."""
    print(red(message))


# ---------------------------------------------------------------------------
# Argument parsing / dispatch
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ezsort",
        description=(
            "EzSort - A smart file organizer that sorts your messy folders\n"
            "into clean categories with a single command. Safe, fast, and\n"
            "completely offline. Never deletes, never overwrites."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ezsort organize ~/Downloads --dry-run   See what would happen\n"
            "  ezsort organize ~/Downloads --yes       Sort it for real\n"
            "  ezsort scan ~/Downloads                  Check folder stats\n"
            "  ezsort undo                              Reverse last sort\n"
            "  ezsort watch ~/Downloads                 Auto-sort new files\n"
            "  ezsort gui                               Open the desktop app\n"
        ),
    )
    parser.add_argument("--version", action="version", version=VERSION_STRING)
    parser.add_argument("--about", action="store_true", help="Show info about EzSort")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-essential output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # organize command
    org_parser = subparsers.add_parser(
        "organize",
        help="Sort a messy folder into neat categories",
        description="Scan a folder, classify files by type, and move them into organized subfolders.",
    )
    org_parser.add_argument("folder", help="Path to the folder to organize")
    org_parser.add_argument("--dry-run", action="store_true", help="Preview changes without touching files")
    org_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    org_parser.add_argument(
        "--recursive", "-r", action="store_true", default=None,
        help="Include subdirectories (overrides the config default)",
    )
    org_parser.add_argument(
        "--include-hidden", action="store_true", default=None,
        help="Also sort hidden files (off by default)",
    )
    org_parser.add_argument(
        "--no-history", action="store_true",
        help="Do not record this run in undo history",
    )

    # scan command
    scan_parser = subparsers.add_parser(
        "scan",
        help="Analyze a folder without moving anything",
        description="Scan a folder and show a breakdown of file types, duplicates, and what could be organized.",
    )
    scan_parser.add_argument("folder", help="Path to scan")
    scan_parser.add_argument(
        "--recursive", "-r", action="store_true", default=None,
        help="Scan subdirectories too (overrides the config default)",
    )
    scan_parser.add_argument(
        "--no-duplicates", action="store_true",
        help="Skip the (slower) duplicate content check",
    )

    # watch command
    watch_parser = subparsers.add_parser(
        "watch",
        help="Auto-sort new files as they appear",
        description="Monitor a folder and automatically organize new files that show up.",
    )
    watch_parser.add_argument("folder", help="Path to watch")
    watch_parser.add_argument("--interval", type=int, default=None,
                              help="Seconds between scans (default: from config, usually 2)")
    watch_parser.add_argument("--recursive", "-r", action="store_true",
                              help="Also watch subdirectories")

    # undo command
    undo_parser = subparsers.add_parser(
        "undo",
        help="Reverse the last sort operation",
        description="Undo the most recent organization and put every file back where it was.",
    )
    undo_parser.add_argument(
        "--batch", "-b", metavar="ID",
        help="Undo a specific batch (see 'ezsort history')",
    )

    # history command
    hist_parser = subparsers.add_parser(
        "history",
        help="See what EzSort has done",
        description="View a log of all past organize operations, including what was moved and when.",
    )
    hist_parser.add_argument("--details", action="store_true", help="Show detailed operation info")
    hist_parser.add_argument("--clear", action="store_true", help="Clear all history")

    # stats command
    subparsers.add_parser(
        "stats",
        help="See your sorting stats",
        description="View cumulative statistics about all your past organize operations.",
    )

    # config command
    subparsers.add_parser(
        "config",
        help="View current settings",
        description="Show the active configuration: categories, rules, excluded dirs, and preferences.",
    )

    # gui command
    subparsers.add_parser(
        "gui",
        help="Launch the EzSort desktop app",
        description="Open the graphical interface (same engine, friendlier controls).",
    )

    # version command
    subparsers.add_parser(
        "version",
        help="Show version info",
        description="Print the current EzSort version.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    global _QUIET
    _QUIET = bool(getattr(args, "quiet", False))

    # Handle --about flag
    if args.about:
        print(ABOUT_TEXT)
        return 0

    # Set up logging
    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.DEBUG
    elif not _QUIET:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="[%(levelname)s] %(message)s",
        stream=sys.stderr,
        force=True,
    )

    if not args.command:
        print(BANNER)
        parser.print_help()
        return 0

    # Dispatch to command handlers
    try:
        if args.command == "organize":
            return cmd_organize(args)
        elif args.command == "scan":
            return cmd_scan(args)
        elif args.command == "watch":
            return cmd_watch(args)
        elif args.command == "undo":
            return cmd_undo(args)
        elif args.command == "history":
            return cmd_history(args)
        elif args.command == "stats":
            return cmd_stats()
        elif args.command == "config":
            return cmd_config()
        elif args.command == "gui":
            return cmd_gui()
        elif args.command == "version":
            print(VERSION_STRING)
            return 0
        else:
            parser.print_help()
            return 0
    except KeyboardInterrupt:
        print("\n  Operation cancelled.")
        return 130
    except BrokenPipeError:  # pragma: no cover - e.g. piping into head
        return 0
    except Exception as e:
        logging.error("Unexpected error: %s", e, exc_info=args.verbose)
        err(f"  Unexpected error: {e}")
        return 1


def _resolve_folder(raw: str) -> Path | None:
    target = Path(raw).expanduser()
    try:
        target = target.resolve()
    except OSError:
        pass
    if not target.exists():
        err(f"  Error: Folder not found: {target}")
        return None
    if not target.is_dir():
        err(f"  Error: Not a directory: {target}")
        return None
    return target


def _recursive_choice(flag: bool | None, config: dict) -> bool:
    """CLI flag wins; otherwise fall back to the configured default."""
    if flag is None:
        return bool(config.get("recursive", False))
    return bool(flag)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_organize(args: argparse.Namespace) -> int:
    """Handle the organize command."""
    target = _resolve_folder(args.folder)
    if target is None:
        return 1

    config = load_config()
    if args.include_hidden:
        config = dict(config)
        config["skip_hidden"] = False
    recursive = _recursive_choice(args.recursive, config)

    say(f"\n  Scanning {target} ...")
    preview = engine.build_preview(target, config=config, recursive=recursive)

    for error in preview.errors:
        warn(f"  Warning: {error}")

    if not preview.files:
        say(yellow("  Nothing to sort here. Folder is clean!"))
        return 0

    say(f"  Found {len(preview.files)} file(s).")
    if preview.skipped:
        say(f"  Skipped {len(preview.skipped)} file(s) (hidden, excluded, or already sorted).")

    if not preview.operations:
        say(yellow("  Everything is already in its place. Nice!"))
        return 0

    # Dry run
    if args.dry_run:
        print(f"\n  {bold('DRY RUN')} -- nothing gets moved\n")
        _print_plan(target, preview.operations)
        print(f"\n  {len(preview.operations)} file(s) would be moved.")
        print("  Run without --dry-run to apply.\n")
        return 0

    # Confirmation
    if not args.yes and config.get("confirm_before_move", True):
        print(f"\n  About to move {len(preview.operations)} file(s):")
        for op in preview.operations[:10]:
            try:
                rel_dest = op.destination.relative_to(target)
            except ValueError:
                rel_dest = op.destination
            marker = " (renamed: name in use)" if op.collision else ""
            print(f"    {op.source.name} -> {rel_dest}{marker}")
        if len(preview.operations) > 10:
            print(f"    ... and {len(preview.operations) - 10} more")
        print()
        answer = input("  Proceed? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("  Cancelled. Nothing was changed.")
            return 0

    # Execute
    print(f"\n  Sorting {len(preview.operations)} file(s) ...")
    summary = engine.run_plan(
        preview,
        dry_run=False,
        record=not args.no_history,
        config=config,
    )

    # Summary
    print(f"\n  {green('Done!')} {summary.moved} file(s) sorted in {summary.elapsed:.2f}s")
    if summary.skipped_duplicates:
        print(
            f"  {len(summary.skipped_duplicates)} duplicate-name move(s) skipped "
            f"(duplicate_strategy = skip)."
        )
    if summary.failed:
        err(f"  {summary.failed} file(s) failed to move:")
        for result in summary.failures[:10]:
            print(f"    - {result.error}")
        if summary.failed > 10:
            print(f"    ... and {summary.failed - 10} more")
    if summary.batch_id:
        print(f"  Batch ID: {summary.batch_id}")
        print("  Undo anytime with: ezsort undo\n")
    elif args.no_history:
        say("  (history recording disabled for this run)")

    return 0 if summary.failed == 0 else 1


def _print_plan(target: Path, operations, limit: int = 200) -> None:
    print(f"  {'File':<30} {'->':<5} {'Destination'}")
    print(f"  {'-'*30} {'-'*5} {'-'*30}")
    for op in operations[:limit]:
        try:
            rel_source = op.source.relative_to(target)
        except ValueError:
            rel_source = op.source.name
        try:
            rel_dest = op.destination.relative_to(target)
        except ValueError:
            rel_dest = op.destination
        marker = ""
        if op.collision:
            try:
                final = get_unique_destination(op.destination)
                marker = f"   [renamed -> {final.name}]"
            except RuntimeError:
                marker = "   [rename pending]"
        print(f"  {str(rel_source):<30} {'->':<5} {rel_dest}{marker}")
    if len(operations) > limit:
        print(f"  ... and {len(operations) - limit} more")


def cmd_scan(args: argparse.Namespace) -> int:
    """Handle the scan command."""
    target = _resolve_folder(args.folder)
    if target is None:
        return 1

    config = load_config()
    recursive = _recursive_choice(args.recursive, config)

    preview = engine.build_preview(
        target,
        config=config,
        recursive=recursive,
        count_duplicates=not args.no_duplicates,
    )

    # Directory count (top level, tolerant of unreadable entries)
    dir_count = 0
    try:
        for entry in target.iterdir():
            try:
                if entry.is_dir() and not entry.is_symlink():
                    dir_count += 1
            except OSError:
                continue
    except OSError as e:
        warn(f"  Warning: Cannot list {target}: {e}")

    if not preview.files and not preview.operations:
        say(yellow("  Folder is empty. Nothing to scan."))
        for error in preview.errors:
            warn(f"  Warning: {error}")
        return 1 if preview.errors else 0

    print(f"\n  {bold('Scan Report')}")
    print(f"  {'='*30}")
    print(f"  Files found:        {len(preview.files)}")
    print(f"  Directories:        {dir_count}")
    if preview.total_size:
        from ezsort.utils import format_size
        print(f"  Total size:         {format_size(preview.total_size)}")
    print()
    for cat in CATEGORY_ORDER:
        count = preview.categories.get(cat, 0)
        if count > 0:
            print(f"  {cat + ':':<20} {count}")
    print()
    print(f"  Potential duplicates: {preview.duplicates}")
    print(f"  Organizable files:    {len(preview.operations)}")
    if preview.skipped:
        print(f"  Skipped files:        {len(preview.skipped)}")
    for error in preview.errors:
        warn(f"  Warning: {error}")
    print()

    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Handle the watch command."""
    from ezsort.watcher import watch_directory

    target = _resolve_folder(args.folder)
    if target is None:
        return 1

    config = load_config()
    interval = args.interval if args.interval is not None else int(config.get("watch_interval", 2))
    if interval < 1:
        err("  Error: --interval must be at least 1 second.")
        return 1

    watch_directory(
        target,
        interval=interval,
        recursive=bool(args.recursive),
        config=config,
    )
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    """Handle the undo command."""
    if getattr(args, "batch", None):
        success, message = engine.undo_specific_batch(args.batch)
    else:
        success, message = engine.undo_last_batch()
    if success:
        print(green(f"  {message}"))
    else:
        err(f"  {message}")
    return 0 if success else 1


def cmd_history(args: argparse.Namespace) -> int:
    """Handle the history command."""
    if args.clear:
        engine.wipe_history()
        print(green("  History cleared."))
        return 0

    history = engine.load_history()

    if not history:
        print(yellow("  No history yet. Run 'ezsort organize' first."))
        return 0

    if args.details:
        for batch in history:
            print(f"\n  Batch {batch['batch_id']} - {batch['timestamp']}")
            print(f"  Moved: {batch.get('total_moved', 0)} file(s)"
                  + (f", Failed: {batch['total_failed']}"
                     if batch.get("total_failed") else ""))
            for op in batch.get("operations", []):
                status = "" if op.get("status", "moved") == "moved" else "  [FAILED]"
                line = f"    {Path(op['source']).name} -> {op['category']}/{status}"
                if op.get("error"):
                    line += f" ({op['error']})"
                print(line)
    else:
        print(f"\n  {'ID':<6} {'Date':<25} {'Action'}")
        print(f"  {'-'*6} {'-'*25} {'-'*30}")
        for batch in history:
            ts = str(batch.get("timestamp", ""))[:19].replace("T", " ")
            action = f"Organized {batch.get('total_moved', 0)} file(s)"
            failed = batch.get("total_failed", 0)
            if failed:
                action += f", {failed} failed"
            print(f"  {batch['batch_id']:<6} {ts:<25} {action}")
    print()
    return 0


def cmd_stats() -> int:
    """Handle the stats command."""
    stats = engine.stats()

    if not stats["batches"]:
        print(yellow("  No stats yet. Run 'ezsort organize' first."))
        return 0

    print(f"\n  {bold('Your Sorting Stats')}")
    print(f"  {'='*30}")
    print(f"  Total files organized: {stats['total_moved']:,}")
    if stats["total_failed"]:
        print(f"  Failed operations:     {stats['total_failed']:,}")
    print(f"  Sort operations:        {stats['batches']:,}")
    print()
    for cat in CATEGORY_ORDER:
        count = stats["categories"].get(cat, 0)
        if count > 0:
            print(f"  {cat + ':':<20} {count:,}")
    print()
    return 0


def cmd_config() -> int:
    """Handle the config command."""
    from ezsort.config import get_config_path

    config = load_config()

    print(f"\n  {bold('Configuration')}")
    print(f"  {'='*30}")
    print(f"  File: {get_config_path()}")
    print("  Categories:")
    for cat, exts in config.get("categories", {}).items():
        print(f"    {cat}: {len(exts)} extensions")
    print(f"\n  Custom rules: {len(config.get('custom_rules', []))}")
    print(f"  Excluded dirs: {config.get('excluded_dirs', [])}")
    print(f"  Excluded extensions: {config.get('excluded_extensions', [])}")
    print(f"  Confirm before move: {config.get('confirm_before_move', True)}")
    print(f"  Recursive by default: {config.get('recursive', False)}")
    print(f"  Skip hidden files: {config.get('skip_hidden', True)}")
    print(f"  Skip partial downloads: {config.get('skip_partial_downloads', True)}")
    print(f"  Duplicate strategy: {config.get('duplicate_strategy', 'rename')}")
    print(f"  Watch interval: {config.get('watch_interval', 2)}s")
    print(f"  Theme: {config.get('theme', 'dark')}")
    print()
    return 0


def cmd_gui() -> int:
    """Launch the desktop application."""
    try:
        from ezsort.gui import run as run_gui
    except ImportError as e:
        err(f"  Error: The desktop interface needs tkinter ({e}).")
        err("  On Debian/Ubuntu install it with: sudo apt install python3-tk")
        return 1
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
