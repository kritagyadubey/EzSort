"""Scanner robustness: unreadable folders, depth, hidden/symlink policy."""

from __future__ import annotations

import pytest

from ezsort.scanner import scan_directory, scan_directory_ex, scan_for_report


def test_scan_missing_directory_reports_error(tmp_path):
    result = scan_directory_ex(tmp_path / "nope")
    assert result.files == []
    assert result.errors
    assert "does not exist" in result.errors[0]


def test_scan_file_instead_of_directory_reports_error(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    result = scan_directory_ex(f)
    assert result.files == []
    assert result.errors


def test_deep_recursion_does_not_crash(tmp_path):
    deep = tmp_path
    for i in range(60):
        deep = deep / f"level{i}"
    deep.mkdir(parents=True)
    (deep / "deep.txt").write_text("deep")
    (tmp_path / "top.txt").write_text("top")

    files = scan_directory(tmp_path, recursive=True)
    names = {f.path.name for f in files}
    assert names == {"deep.txt", "top.txt"}


def test_excluded_dirs_case_insensitive(tmp_path):
    (tmp_path / "NODE_MODULES").mkdir()
    (tmp_path / "NODE_MODULES" / "lib.js").write_text("x")
    (tmp_path / "keep.txt").write_text("x")

    files = scan_directory(tmp_path, excluded_dirs=["node_modules", ".git"])
    assert [f.path.name for f in files] == ["keep.txt"]


def test_skip_hidden_toggle(tmp_path):
    (tmp_path / ".secret").write_text("hidden")
    (tmp_path / "open.txt").write_text("visible")

    without = scan_directory(tmp_path, skip_hidden=True)
    assert [f.path.name for f in without] == ["open.txt"]

    with_hidden = scan_directory(tmp_path, skip_hidden=False)
    assert {f.path.name for f in with_hidden} == {".secret", "open.txt"}


def test_scan_does_not_follow_symlinked_directories(tmp_path):
    # Real content lives OUTSIDE the scanned tree; the only way to reach
    # it would be by following the symlink.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "inside.txt").write_text("x")
    tree = tmp_path / "tree"
    tree.mkdir()
    link = tree / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not supported")  # type: ignore[undefined]
    result = scan_directory_ex(tree, recursive=True)
    names = {f.path.name for f in result.files}
    assert "inside.txt" not in names  # not reached through the link
    assert result.symlink_skipped >= 1


def test_scan_report_counts_dirs_and_errors(tmp_path):
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub2").mkdir()
    (tmp_path / "file.txt").write_text("x")
    report = scan_for_report(tmp_path, recursive=True)
    assert report.total_files == 1
    # root + two subdirectories
    assert report.directories == 3


def test_scan_sorted_output(tmp_path):
    for name in ("b.txt", "c.txt", "a.txt"):
        (tmp_path / name).write_text("x")
    files = scan_directory(tmp_path)
    assert [f.path.name for f in files] == ["a.txt", "b.txt", "c.txt"]
