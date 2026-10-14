# Changelog

All notable changes to EzSort will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
