"""Tests for the CLI module."""

import pytest
from pathlib import Path
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
    assert "0.1.0" in captured.out


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
    assert "0.1.0" in captured.out


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
