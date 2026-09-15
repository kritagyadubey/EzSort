"""CLI entry point for EzSort."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Sequence

from ezsort import __version__
from ezsort.constants import BANNER, CATEGORY_ORDER, VERSION_STRING
from ezsort.scanner import scan_directory
from ezsort.classifier import classify_batch
from ezsort.planner import create_plan
from ezsort.organizer import execute_operations
from ezsort.history import record_operations, undo_last, get_history, clear_history
from ezsort.duplicate import find_duplicates
from ezsort.config import load_config
from ezsort.utils import green, red, yellow, cyan, bold


ABOUT_TEXT = f"""
  {bold('EzSort')} v{__version__}
  Keep Your Files Sorted, Effortlessly.

  Made by Kritagya Dubey
  GitHub: https://github.com/kritagyadubey/EzSort
  License: MIT
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point."""
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
    org_parser.add_argument("--recursive", "-r", action="store_true", help="Include subdirectories")

    # scan command
    scan_parser = subparsers.add_parser(
        "scan",
        help="Analyze a folder without moving anything",
        description="Scan a folder and show a breakdown of file types, duplicates, and what could be organized.",
    )
    scan_parser.add_argument("folder", help="Path to scan")
    scan_parser.add_argument("--recursive", "-r", action="store_true", help="Scan subdirectories too")

    # watch command
    watch_parser = subparsers.add_parser(
        "watch",
        help="Auto-sort new files as they appear",
        description="Monitor a folder and automatically organize new files that show up.",
    )
    watch_parser.add_argument("folder", help="Path to watch")
    watch_parser.add_argument("--interval", type=int, default=2, help="Seconds between scans (default: 2)")

    # undo command
    subparsers.add_parser(
        "undo",
        help="Reverse the last sort operation",
        description="Undo the most recent organization and put every file back where it was.",
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

    # version command
    subparsers.add_parser(
        "version",
        help="Show version info",
        description="Print the current EzSort version.",
    )

    args = parser.parse_args(argv)

    # Handle --about flag
    if args.about:
        print(ABOUT_TEXT)
        return 0

    # Set up logging
    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.DEBUG
    elif not hasattr(args, "quiet") or not getattr(args, "quiet", False):
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="[%(levelname)s] %(message)s",
        stream=sys.stderr,
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
            return cmd_undo()
        elif args.command == "history":
            return cmd_history(args)
        elif args.command == "stats":
            return cmd_stats()
        elif args.command == "config":
            return cmd_config()
        elif args.command == "version":
            print(VERSION_STRING)
            return 0
        else:
            parser.print_help()
            return 0
    except KeyboardInterrupt:
        print("\n  Operation cancelled.")
        return 130
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        return 1


def cmd_organize(args: argparse.Namespace) -> int:
    """Handle the organize command."""
    target = Path(args.folder).expanduser().resolve()

    if not target.exists():
        print(red(f"  Error: Folder not found: {target}"))
        return 1
    if not target.is_dir():
        print(red(f"  Error: Not a directory: {target}"))
        return 1

    config = load_config()

    print(f"\n  Scanning {target} ...")
    files = scan_directory(target, recursive=args.recursive)

    if not files:
        print(yellow("  Nothing to sort here. Folder is clean!"))
        return 0

    print(f"  Found {len(files)} file(s).")

    # Classify
    classified = classify_batch(files, config)

    # Plan
    plan = create_plan(classified, target)

    if not plan:
        print(yellow("  Everything is already in its place. Nice!"))
        return 0

    # Dry run
    if args.dry_run:
        print(f"\n  {bold('DRY RUN')} -- nothing gets moved\n")
        print(f"  {'File':<30} {'->':<5} {'Destination'}")
        print(f"  {'-'*30} {'-'*5} {'-'*30}")
        for op in plan:
            try:
                rel_source = op.source.relative_to(target)
            except ValueError:
                rel_source = op.source.name
            try:
                rel_dest = op.destination.relative_to(target)
            except ValueError:
                rel_dest = op.destination
            print(f"  {str(rel_source):<30} {'->':<5} {rel_dest}")
        print(f"\n  {len(plan)} file(s) would be moved.")
        print(f"  Run without --dry-run to apply.\n")
        return 0

    # Confirmation
    if not args.yes and config.get("confirm_before_move", True):
        print(f"\n  About to move {len(plan)} file(s):")
        for op in plan[:10]:
            try:
                rel_dest = op.destination.relative_to(target)
            except ValueError:
                rel_dest = op.destination
            print(f"    {op.source.name} -> {rel_dest}")
        if len(plan) > 10:
            print(f"    ... and {len(plan) - 10} more")
        print()
        answer = input("  Proceed? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("  Cancelled. Nothing was changed.")
            return 0

    # Execute
    print(f"\n  Sorting {len(plan)} file(s) ...")
    start_time = time.time()
    results = execute_operations(plan, dry_run=False)
    elapsed = time.time() - start_time

    # Record history
    batch_id = record_operations(results)

    # Summary
    moved = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    print(f"\n  {green('Done!')} {moved} file(s) sorted in {elapsed:.2f}s")
    if failed:
        print(f"  {red(f'{failed} file(s) failed to move.')}")
    print(f"  Batch ID: {batch_id}")
    print(f"  Undo anytime with: ezsort undo\n")

    return 0 if failed == 0 else 1


def cmd_scan(args: argparse.Namespace) -> int:
    """Handle the scan command."""
    target = Path(args.folder).expanduser().resolve()

    if not target.exists():
        print(red(f"  Error: Folder not found: {target}"))
        return 1
    if not target.is_dir():
        print(red(f"  Error: Not a directory: {target}"))
        return 1

    config = load_config()
    files = scan_directory(target, recursive=args.recursive)

    if not files:
        print(yellow("  Folder is empty. Nothing to scan."))
        return 0

    # Classify for category counts
    classified = classify_batch(files, config)
    category_counts: dict[str, int] = {}
    for _, category, _ in classified:
        top = category.split("/")[0]
        category_counts[top] = category_counts.get(top, 0) + 1

    # Duplicate check
    file_paths = [f.path for f in files if f.path.is_file()]
    duplicates = find_duplicates(file_paths)
    duplicate_count = sum(len(paths) - 1 for paths in duplicates.values())

    # Count organizable
    plan = create_plan(classified, target)
    organizable = len(plan)

    print(f"\n  {bold('Scan Report')}")
    print(f"  {'='*30}")
    print(f"  Files found:        {len(files)}")
    print(f"  Directories:        {sum(1 for f in target.iterdir() if f.is_dir())}")
    print()
    for cat in CATEGORY_ORDER:
        count = category_counts.get(cat, 0)
        if count > 0:
            print(f"  {cat + ':':<20} {count}")
    others = category_counts.get("Others", 0)
    if others:
        print(f"  {'Others:':<20} {others}")
    print()
    print(f"  Potential duplicates: {duplicate_count}")
    print(f"  Organizable files:    {organizable}")
    print()

    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Handle the watch command."""
    from ezsort.watcher import watch_directory

    target = Path(args.folder).expanduser().resolve()

    if not target.exists():
        print(red(f"  Error: Folder not found: {target}"))
        return 1
    if not target.is_dir():
        print(red(f"  Error: Not a directory: {target}"))
        return 1

    config = load_config()
    watch_directory(target, interval=args.interval, config=config)
    return 0


def cmd_undo() -> int:
    """Handle the undo command."""
    success, message = undo_last()
    if success:
        print(green(f"  {message}"))
    else:
        print(red(f"  {message}"))
    return 0 if success else 1


def cmd_history(args: argparse.Namespace) -> int:
    """Handle the history command."""
    if args.clear:
        clear_history()
        print(green("  History cleared."))
        return 0

    history = get_history()

    if not history:
        print(yellow("  No history yet. Run 'ezsort organize' first."))
        return 0

    if args.details:
        for batch in history:
            print(f"\n  Batch {batch['batch_id']} - {batch['timestamp']}")
            print(f"  Moved: {batch['total_moved']} file(s)")
            for op in batch.get("operations", []):
                print(f"    {Path(op['source']).name} -> {op['category']}/")
    else:
        print(f"\n  {'ID':<6} {'Date':<25} {'Action'}")
        print(f"  {'-'*6} {'-'*25} {'-'*30}")
        for batch in history:
            ts = batch["timestamp"][:19].replace("T", " ")
            print(f"  {batch['batch_id']:<6} {ts:<25} Organized {batch['total_moved']} file(s)")
    print()
    return 0


def cmd_stats() -> int:
    """Handle the stats command."""
    history = get_history()

    if not history:
        print(yellow("  No stats yet. Run 'ezsort organize' first."))
        return 0

    total = 0
    category_totals: dict[str, int] = {}

    for batch in history:
        total += batch.get("total_moved", 0)
        for op in batch.get("operations", []):
            cat = op.get("category", "Others").split("/")[0]
            category_totals[cat] = category_totals.get(cat, 0) + 1

    print(f"\n  {bold('Your Sorting Stats')}")
    print(f"  {'='*30}")
    print(f"  Total files organized: {total:,}")
    print()
    for cat in CATEGORY_ORDER:
        count = category_totals.get(cat, 0)
        if count > 0:
            print(f"  {cat + ':':<20} {count:,}")
    print()
    return 0


def cmd_config() -> int:
    """Handle the config command."""
    config = load_config()

    print(f"\n  {bold('Configuration')}")
    print(f"  {'='*30}")
    print(f"  Categories:")
    for cat, exts in config.get("categories", {}).items():
        print(f"    {cat}: {len(exts)} extensions")
    print(f"\n  Custom rules: {len(config.get('custom_rules', []))}")
    print(f"  Excluded dirs: {config.get('excluded_dirs', [])}")
    print(f"  Confirm before move: {config.get('confirm_before_move', True)}")
    print(f"  Duplicate strategy: {config.get('duplicate_strategy', 'rename')}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
