# Changelog

All notable changes to EzSort will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.3.0] - 2026-10-15

A stability-and-polish release. No new commands; the focus was making
every existing path correct, and making the desktop app feel finished.

### Fixed

- **Every GUI sort failed.** `organizer.sort_files()` passed a
  `cancel_check` name that no longer existed after the per-task cancel
  token refactor, so *every* run ended with "Sorting failed: name
  'cancel_check' is not defined" without moving a file. The cancel
  callback is now defined inside the worker and wired to the token that
  run actually owns.
- **Stale previews could sort the wrong folder.** Picking a new folder
  while a scan of the previous one was still running let the old result
  land afterwards, so the table showed a plan for a folder the user had
  already left. Scans now carry a sequence number and superseded results
  are dropped; changing folder or options invalidates in-flight scans.
- **"Sort unfinished downloads too" was inverted.** The checkbox wrote
  the opposite of what it offered, so ticking it *stopped* partial
  downloads being sorted and unticking them let half-finished
  `.crdownload`/`.part` files be moved mid-download.
- **Cancel could hit the wrong task.** A single shared cancel token meant
  the Organizer's Cancel button could cancel watch mode (and vice versa).
  Tokens are now per-task, keyed by label.
- **Busy indicator lied.** It reported "Idle" while watch mode or another
  task was still running; it now reflects whatever is actually alive.
- **Light theme leaks.** The sidebar brand block and its separators are
  plain Tk widgets, so a theme switch left them in the old palette — a
  black block in light mode. They are now recolored explicitly.
- **Clipped summary line.** `Page.__init__` gives the body's first row
  `weight=1`, so in a short window grid shrank the Organizer's options
  card and cut the "N file(s) scanned | N move(s) planned" summary in
  half. Only the scrollable table row flexes now (Organizer, History and
  Activity).
- **History details mismatched duplicate filenames.** Selecting a row in
  the batch detail table resolved files by name, so two files with the
  same name showed the wrong one. Rows are now keyed by operation index.
- **Frozen EXE lost its icon.** The build bundles it into `packaging/`
  inside the bundle, but the runtime lookup only checked the bundle root.
- **Misleading stat label.** The dashboard's "Files last organized" now
  reads "Files organized (all time)", matching the cumulative number it
  actually displays.
- Watch-mode history was written once per moved file (one full file
  rewrite each); a wave of downloads is now recorded as a single
  undoable batch, flushed on a quiet poll and on exit.
- Watch mode no longer writes to stdout when driven by the GUI (a
  windowed EXE has no console); the CLI keeps its full output.

### Changed

- Dark and light palettes were rebuilt for legibility; both now clear
  WCAG AA (4.5:1) for body text, muted text, the accent button label and
  the status colors used in tables.
- Visible keyboard focus on entries, comboboxes and buttons, plus
  `Ctrl+1..6` page navigation and `F5` refresh.
- Tables use striped rows and consistent moved/failed/skipped/rename
  colors across every page.
- Per-Monitor V2 DPI awareness, so the window is crisp on mixed-scale
  displays.
- The real app icon is used for the window and taskbar (source and
  frozen builds); executables embed Windows version metadata, so
  Explorer's Properties shows the product name, version and author.
- Organizer progress updates use a source-path lookup instead of
  rescanning the table per file.

### Added

- Desktop-app tests (`tests/test_gui.py`) covering palettes, contrast,
  theming, navigation, per-task cancellation, and end-to-end preview /
  sort / cancel runs. They build the real Tk app and skip cleanly when Tk
  is unavailable.
- Watch-mode batching tests, and regression tests for each fix above.
- `scripts/verify_cli_exe.py` and `scripts/verify_gui_exe.py`: end-to-end
  checks of the *built* executables on disposable temp folders.

## [0.2.0] - 2026-10-13

### Added

- **Desktop app (premium dark theme)** — a full Tkinter GUI with six pages:
  dashboard, organizer, categories, history, activity log, and settings
  (theme switcher dark/light, persistent window geometry).
- Shared `ezsort.engine` facade so the CLI and GUI use identical
  preview, execute, and undo logic.
- New `ezsort gui` command and `ezsort-gui` console script.
- Watch mode is available in the GUI with start/stop controls and live events.
- Batch-scoped undo (`ezsort undo --batch ID`) alongside undo-last.
- `EZSORT_HOME` environment variable to relocate EzSort's config/data
  directory (useful for tests, portable installs, and CI).
- Activity/event log surfaced in the GUI and stored with history.
- PyInstaller specs and a generated multi-resolution app icon
  (`packaging/ezsort-gui.spec`, `packaging/ezsort-cli.spec`,
  `packaging/ezsort.ico`); scripts produce a windowed `EzSort.exe` and a
  console `ezsort.exe`.
- GitHub Actions workflow that builds both Windows executables on every
  push and attaches them to a GitHub Release when a `v*` tag is pushed.
- New tests for the engine facade, planner safety, config/scanner
  robustness, and the watcher; GUI smoke-test script with screenshots.

### Changed

- Organizer records the destination folder in undo history, re-checks for
  collisions right before each move, and skips files already inside their
  own category folder (recursive runs are now idempotent).
- Config loading merges user settings over defaults and validates values;
  corrupt config files are backed up instead of crashing.
- Scanner is iterative (deep trees are safe) and collects per-file errors
  instead of aborting the scan.
- `duplicate_strategy=skip` is now genuinely honored.
- CLI `--quiet` now suppresses all informational output; clearer exit codes.
- README, screenshots, and docs refreshed; dependency files split into
  `requirements.txt` (empty — stdlib only) and `requirements-dev.txt`.

### Fixed

- Undo no longer overwrites files that have reappeared at their original
  paths; conflicting entries stay in history for retry.
- Long-path handling and non-ASCII names on Windows.
- Atomic writes for config/history files (no truncation on crash).

## [0.1.0] - 2026-09-15

### Added

- Initial release of EzSort
- File organization by extension into 13 categories
- Dry-run mode for safe preview
- Undo support with history tracking
- SHA-256 duplicate file detection
- Custom classification rules (extension, filename patterns)
- Watch mode for automatic organization
- Recursive mode (opt-in)
- Cross-platform support (Windows, macOS, Linux)
- Comprehensive CLI with multiple commands
- Configuration system with platform-appropriate paths
- Duplicate-safe file handling (never overwrites)
- Protection of EzSort's own folders from processing
- Symlink and hidden file handling
- Verbose and quiet output modes
- Complete test suite
