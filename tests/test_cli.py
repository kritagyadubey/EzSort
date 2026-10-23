"""Tests for the CLI module."""

import pytest
from ezsort import __version__
from ezsort.cli import main


@pytest.fixture
def cli_dir(tmp_path):
    """Create a test directory for CLI tests."""
    (tmp_path / "photo.jpg").write_bytes(b"fake image")
    (tmp_path / "resume.pdf").write_bytes(b"fake pdf")
    (tmp_path / "song.mp3").write_bytes(b"fake audio")
    return tmp_path


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_cli_no_command(capsys):
    result = main([])
    assert result == 0


def test_cli_organize_dry_run(cli_dir, capsys):
    result = main(["organize", str(cli_dir), "--dry-run", "--yes"])
    assert result == 0
    captured = capsys.readouterr()
    assert "Dry Run" in captured.out or "dry" in captured.out.lower()
    # Files should NOT be moved
    assert (cli_dir / "photo.jpg").exists()
    assert (cli_dir / "resume.pdf").exists()


def test_cli_scan(cli_dir, capsys):
    result = main(["scan", str(cli_dir)])
    assert result == 0
    captured = capsys.readouterr()
    assert "Files found" in captured.out


def test_cli_scan_nonexistent(capsys):
    result = main(["scan", "/nonexistent/path"])
    assert result == 1


def test_cli_organize_nonexistent(capsys):
    result = main(["organize", "/nonexistent/path"])
    assert result == 1


def test_cli_organize_actual(cli_dir):
    result = main(["organize", str(cli_dir), "--yes"])
    assert result == 0
    # Files should be moved
    assert (cli_dir / "Images" / "photo.jpg").exists()
    assert (cli_dir / "Documents" / "resume.pdf").exists()
    assert (cli_dir / "Music" / "song.mp3").exists()


def test_cli_undo(cli_dir, capsys):
    # First organize
    main(["organize", str(cli_dir), "--yes"])
    assert (cli_dir / "Images" / "photo.jpg").exists()
    
    # Then undo
    result = main(["undo"])
    assert result == 0
    assert (cli_dir / "photo.jpg").exists()


def test_cli_history(cli_dir, capsys):
    # Organize first
    main(["organize", str(cli_dir), "--yes"])
    
    result = main(["history"])
    assert result == 0
    captured = capsys.readouterr()
    assert "Batch" in captured.out or "Organized" in captured.out


def test_cli_stats(cli_dir, capsys):
    result = main(["stats"])
    assert result == 0


def test_cli_config(capsys):
    result = main(["config"])
    assert result == 0
    captured = capsys.readouterr()
    assert "Categories" in captured.out


def test_cli_version_command(capsys):
    result = main(["version"])
    assert result == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_organize_with_unicode(cli_dir):
    # Create a file with unicode name
    unicode_file = cli_dir / "données.xlsx"
    unicode_file.write_bytes(b"spreadsheet")
    
    result = main(["organize", str(cli_dir), "--yes"])
    assert result == 0
    assert (cli_dir / "Spreadsheets" / "données.xlsx").exists()


def test_cli_organize_spaces_in_name(cli_dir):
    space_file = cli_dir / "my document.txt"
    space_file.write_text("content")
    
    result = main(["organize", str(cli_dir), "--yes"])
    assert result == 0
    assert (cli_dir / "Documents" / "my document.txt").exists()


def test_cli_organize_idempotent(cli_dir):
    # Run twice - second should have nothing to do
    main(["organize", str(cli_dir), "--yes"])
    result = main(["organize", str(cli_dir), "--yes", "--dry-run"])
    assert result == 0


#: A folder that exercises moves, category folders, hidden files and a
#: partial download, so the comparison covers both "moved" and "skipped".
GOLDEN_FILES = {
    "photo.jpg": b"jpeg",
    "holiday.png": b"png",
    "report.pdf": b"pdf",
    "notes.txt": b"text",
    "song.mp3": b"audio",
    "movie.mp4": b"video",
    "backup.zip": b"zip",
    "script.py": b"code",
    "budget.csv": b"csv",
    "slides.pptx": b"pptx",
    ".hidden.jpg": b"hidden",
    "leftover.crdownload": b"partial",
}


def _relative_tree(root):
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )


def test_cli_and_gui_engine_produce_the_same_tree(tmp_path):
    """CLI golden parity: both front ends execute one identical plan.

    The GUI previews with ``engine.build_preview`` and the CLI parses
    arguments around the same function. Running each against an identical
    copy of a synthetic folder must produce byte-for-byte identical trees,
    including the files both deliberately leave alone.
    """
    from ezsort import engine
    from ezsort.config import load_config

    cli_dir = tmp_path / "cli-downloads"
    gui_dir = tmp_path / "gui-downloads"
    for folder in (cli_dir, gui_dir):
        folder.mkdir()
        for name, content in GOLDEN_FILES.items():
            (folder / name).write_bytes(content)

    config = load_config()
    preview = engine.build_preview(gui_dir, config=config, recursive=False)
    engine.run_plan(preview, config=config)

    assert main(["organize", str(cli_dir), "--yes"]) == 0

    gui_tree = _relative_tree(gui_dir)
    assert gui_tree == _relative_tree(cli_dir), (
        "the CLI and the GUI engine disagree about where files belong"
    )
    # The shared plan is real, not two empty trees.
    assert "Images/photo.jpg" in gui_tree
    assert "Documents/report.pdf" in gui_tree
    assert "Music/song.mp3" in gui_tree
    assert ".hidden.jpg" in gui_tree, "hidden files must stay put"
    assert "leftover.crdownload" in gui_tree, "partials must stay put"
