# EzSort

> Your downloads folder is a disaster. EzSort fixes that in one command.

---

## What does EzSort do?

It takes a messy folder and sorts every file into neat subfolders based on what kind of file it is.

**Before:**
```
Downloads/
  vacation.jpg
  gf.png
  resume.pdf
  tax-return.pdf
  concert.mp4
  playlist.mp3
  backup.zip
  setup.exe
  app.py
  budget.csv
  presentation.pptx
  .DS_Store
  MyProject/
```

**After `ezsort organize ~/Downloads`:**
```
Downloads/
  Images/
    vacation.jpg
    gf.png
  Documents/
    tax-return.pdf
    resume.pdf
  Videos/
    concert.mp4
  Music/
    playlist.mp3
  Archives/
    backup.zip
  Applications/
    setup.exe
  Code/
    app.py
  Spreadsheets/
    budget.csv
  Presentations/
    presentation.pptx
  MyProject/          <- untouched
```

No files deleted. No files overwritten. Just organized.

---

## Install

```bash
pip install ezsort
```

That's it. Zero dependencies. Works on Windows, macOS, and Linux.

---

## Quick Start

```bash
# Preview what would happen (nothing gets moved)
ezsort organize ~/Downloads --dry-run

# Actually sort the folder
ezsort organize ~/Downloads --yes

# Scan a folder to see what's in it
ezsort scan ~/Downloads

# Undo the last sort
ezsort undo
```

---

## Commands

### `organize` -- Sort a folder

```bash
ezsort organize ~/Downloads              # Interactive (asks before moving)
ezsort organize ~/Downloads --yes        # Skip confirmation
ezsort organize ~/Downloads --dry-run    # Preview only
ezsort organize ~/Downloads -r           # Include subfolders
```

### `scan` -- Look without touching

```bash
ezsort scan ~/Downloads
```

Shows file counts by category, potential duplicates, and how many files could be organized.

### `watch` -- Auto-sort new files

```bash
ezsort watch ~/Downloads
```

Keeps a folder sorted automatically. New files get moved as they appear. Press `Ctrl+C` to stop.

### `undo` -- Take it back

```bash
ezsort undo
```

Reverses the last sort operation. Every file goes back to where it was.

### `history` -- See what happened

```bash
ezsort history              # List of past operations
ezsort history --details    # Show individual files per operation
ezsort history --clear      # Wipe the history
```

### `stats` -- Your sorting numbers

```bash
ezsort stats
```

Shows total files organized and breakdown by category.

### `config` -- View settings

```bash
ezsort config
```

Shows categories, custom rules, excluded directories, and preferences.

### `--about` -- About EzSort

```bash
ezsort --about
```

Shows version, author, and GitHub repo info.

---

## Flags

| Flag | What it does |
|------|-------------|
| `--help` | Show help for any command |
| `--version` | Print version number |
| `--verbose`, `-v` | Show detailed logs |
| `--quiet`, `-q` | Suppress extra output |
| `--dry-run` | Preview without moving files |
| `--yes`, `-y` | Skip confirmation prompt |
| `--recursive`, `-r` | Include subdirectories |

---

## How it works

1. **Scan** -- EzSort walks through your folder and finds every file
2. **Classify** -- Each file gets matched to a category by its extension (140+ types supported)
3. **Plan** -- It builds a list of moves, skipping files that are already in the right place
4. **Execute** -- Files get moved into their category folders
5. **Record** -- Everything is logged so you can undo it later

---

## Safe by design

EzSort will never:

- Delete your files
- Overwrite existing files (duplicates get renamed: `report.pdf` -> `report (1).pdf`)
- Extract archives
- Move folders (only files)
- Upload anything
- Require internet access

It skips hidden files, symlinks, and its own working directories.

---

## Custom rules

Create a config file to add your own classification rules:

- **Windows:** `%APPDATA%/EzSort/config.json`
- **Linux:** `~/.config/ezsort/config.json`
- **macOS:** `~/Library/Application Support/ezsort/config.json`

Example:

```json
{
  "custom_rules": [
    {
      "type": "extension",
      "pattern": ".psd",
      "category": "Design"
    },
    {
      "type": "filename_contains",
      "pattern": "invoice",
      "category": "Documents/Invoices"
    },
    {
      "type": "filename_contains",
      "pattern": "college",
      "category": "Education"
    }
  ]
}
```

Custom rules override the default categories. Priority goes top to bottom.

---

## Supported file types

EzSort recognizes **140+ file extensions** across 12 categories:

| Category | Examples |
|----------|----------|
| Images | `.jpg`, `.png`, `.gif`, `.webp`, `.heic`, `.raw`, `.psd` |
| Videos | `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm` |
| Music | `.mp3`, `.wav`, `.flac`, `.m4a`, `.ogg` |
| Documents | `.pdf`, `.docx`, `.txt`, `.md`, `.rtf` |
| Spreadsheets | `.xlsx`, `.csv`, `.ods`, `.tsv` |
| Presentations | `.pptx`, `.key`, `.odp` |
| Archives | `.zip`, `.rar`, `.7z`, `.tar.gz`, `.dmg` |
| Applications | `.exe`, `.msi`, `.deb`, `.apk`, `.app` |
| Code | `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.go`, `.rs`, `.html` |
| Fonts | `.ttf`, `.otf`, `.woff2` |
| Ebooks | `.epub`, `.mobi`, `.azw3` |
| Torrents | `.torrent` |

---

## Platform support

- Windows 10/11
- macOS 10.15+
- Linux (Ubuntu, Fedora, Debian, Arch, etc.)
- Requires Python 3.8+

---

## Troubleshooting

**"command not found: ezsort"**

Make sure the package is installed:

```bash
pip install ezsort
```

Or run it as a Python module:

```bash
python -m ezsort organize ~/Downloads
```

**"Permission denied"**

Some system folders need elevated permissions. Try running with appropriate access for that specific folder.

**Files not being organized**

Add `--verbose` to see what's happening:

```bash
ezsort organize ~/Downloads --verbose
```

---

## Development

```bash
git clone https://github.com/kritagyadubey/EzSort.git
cd EzSort
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License -- see [LICENSE](LICENSE) for details.

---

## Author

Built by **Kritagya Dubey**

- GitHub: [github.com/kritagyadubey/EzSort](https://github.com/kritagyadubey/EzSort)
- Issues: [github.com/kritagyadubey/EzSort/issues](https://github.com/kritagyadubey/EzSort/issues)

> Keep Your Files Sorted, Effortlessly.
