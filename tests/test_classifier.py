"""Tests for the file classifier module."""

import pytest
from pathlib import Path
from ezsort.classifier import classify_file, classify_batch, _match_custom_rule
from ezsort.models import FileItem
from ezsort.config import get_default_config


@pytest.fixture
def tmp_files(tmp_path):
    """Create temporary test files."""
    files = {}
    for name in [
        "photo.jpg", "resume.pdf", "movie.mp4", "song.mp3",
        "project.zip", "setup.exe", "script.py", "notes.txt",
        "data.csv", "slides.pptx", "font.ttf", "book.epub",
        "download.torrent", "unknown.xyz",
    ]:
        p = tmp_path / name
        p.write_text("test content")
        files[name] = p
    return files


def test_classify_images(tmp_files):
    item = FileItem(path=tmp_files["photo.jpg"])
    category, reason = classify_file(item)
    assert category == "Images"
    assert ".jpg" in reason


def test_classify_documents(tmp_files):
    item = FileItem(path=tmp_files["resume.pdf"])
    category, reason = classify_file(item)
    assert category == "Documents"


def test_classify_videos(tmp_files):
    item = FileItem(path=tmp_files["movie.mp4"])
    category, reason = classify_file(item)
    assert category == "Videos"


def test_classify_music(tmp_files):
    item = FileItem(path=tmp_files["song.mp3"])
    category, reason = classify_file(item)
    assert category == "Music"


def test_classify_archives(tmp_files):
    item = FileItem(path=tmp_files["project.zip"])
    category, reason = classify_file(item)
    assert category == "Archives"


def test_classify_applications(tmp_files):
    item = FileItem(path=tmp_files["setup.exe"])
    category, reason = classify_file(item)
    assert category == "Applications"


def test_classify_code(tmp_files):
    item = FileItem(path=tmp_files["script.py"])
    category, reason = classify_file(item)
    assert category == "Code"


def test_classify_spreadsheets(tmp_files):
    item = FileItem(path=tmp_files["data.csv"])
    category, reason = classify_file(item)
    assert category == "Spreadsheets"


def test_classify_presentations(tmp_files):
    item = FileItem(path=tmp_files["slides.pptx"])
    category, reason = classify_file(item)
    assert category == "Presentations"


def test_classify_fonts(tmp_files):
    item = FileItem(path=tmp_files["font.ttf"])
    category, reason = classify_file(item)
    assert category == "Fonts"


def test_classify_ebooks(tmp_files):
    item = FileItem(path=tmp_files["book.epub"])
    category, reason = classify_file(item)
    assert category == "Ebooks"


def test_classify_torrents(tmp_files):
    item = FileItem(path=tmp_files["download.torrent"])
    category, reason = classify_file(item)
    assert category == "Torrents"


def test_classify_unknown_extension(tmp_files):
    item = FileItem(path=tmp_files["unknown.xyz"])
    category, reason = classify_file(item)
    assert category == "Others"


def test_classify_uppercase_extension(tmp_path):
    f = tmp_path / "PHOTO.JPG"
    f.write_text("test")
    item = FileItem(path=f)
    category, _ = classify_file(item)
    assert category == "Images"


def test_classify_custom_rule_extension(tmp_files):
    config = get_default_config()
    config["custom_rules"] = [
        {"type": "extension", "pattern": ".psd", "category": "Design"}
    ]
    # Create a PSD file
    psd = tmp_files["photo.jpg"].parent / "design.psd"
    psd.write_text("test")
    item = FileItem(path=psd)
    category, reason = classify_file(item, config)
    assert category == "Design"


def test_classify_custom_rule_filename_contains(tmp_files):
    config = get_default_config()
    config["custom_rules"] = [
        {"type": "filename_contains", "pattern": "invoice", "category": "Documents/Invoices"}
    ]
    inv = tmp_files["notes.txt"].parent / "invoice_2026.pdf"
    inv.write_text("test")
    item = FileItem(path=inv)
    category, reason = classify_file(item, config)
    assert category == "Documents/Invoices"


def test_classify_custom_rule_priority(tmp_files):
    config = get_default_config()
    config["custom_rules"] = [
        {"type": "extension", "pattern": ".pdf", "category": "SpecialDocs"}
    ]
    item = FileItem(path=tmp_files["resume.pdf"])
    category, _ = classify_file(item, config)
    assert category == "SpecialDocs"


def test_classify_batch(tmp_files):
    items = [FileItem(path=p) for p in tmp_files.values()]
    results = classify_batch(items)
    assert len(results) == len(tmp_files)
    for item, category, reason in results:
        assert category in ["Images", "Documents", "Videos", "Music", "Archives",
                           "Applications", "Code", "Spreadsheets", "Presentations",
                           "Fonts", "Ebooks", "Torrents", "Others"]
        assert len(reason) > 0
