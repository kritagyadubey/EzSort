"""Safety-focused planner tests: traversal, idempotency, collisions."""

from __future__ import annotations


from ezsort.models import FileItem
from ezsort.planner import create_plan, create_plan_detailed


def test_malicious_category_cannot_escape_target(tmp_path):
    """A custom rule with '../..' must never move files outside the folder."""
    folder = tmp_path / "target"
    folder.mkdir()
    victim = folder / "important.pdf"
    victim.write_text("data")

    classified = [(FileItem(path=victim), "../../outside", "hostile rule")]
    result = create_plan_detailed(classified, folder)

    # Either refused outright, or contained inside the target folder.
    for op in result.operations:
        resolved = op.destination.resolve()
        assert str(resolved).startswith(str(folder.resolve()))
    if not result.operations:
        assert result.skipped  # reason recorded


def test_windows_illegal_category_chars_sanitized(tmp_path):
    folder = tmp_path / "target"
    folder.mkdir()
    f = folder / "a.txt"
    f.write_text("x")

    classified = [(FileItem(path=f), 'Con:Invoices<>|?"*', "weird")]
    result = create_plan_detailed(classified, folder)
    assert len(result.operations) == 1
    dest = result.operations[0].destination
    # Every path component must be free of Windows-illegal characters.
    for part in dest.relative_to(folder).parts:
        for ch in '<>:"|?*':
            assert ch not in part


def test_already_in_category_folder_is_not_reshuffled(tmp_path):
    """Files inside their own category folder stay put on every run."""
    folder = tmp_path / "target"
    docs = folder / "Documents"
    sub = docs / "archive-2025"
    sub.mkdir(parents=True)
    f = sub / "old-report.pdf"
    f.write_text("x")

    classified = [(FileItem(path=f), "Documents", "ext")]
    result = create_plan_detailed(classified, folder)
    assert result.operations == []
    assert result.skipped


def test_plan_marks_destination_collisions(tmp_path):
    folder = tmp_path / "target"
    folder.mkdir()
    (folder / "Images").mkdir()
    (folder / "Images" / "pic.jpg").write_text("existing")
    src = folder / "pic.jpg"
    src.write_text("incoming")

    classified = [(FileItem(path=src), "Images", "ext")]
    result = create_plan_detailed(classified, folder)
    assert len(result.operations) == 1
    assert result.operations[0].collision is True


def test_operation_ids_unique_per_move(tmp_path):
    folder = tmp_path / "target"
    folder.mkdir()
    a = folder / "a.jpg"
    a.write_text("x")
    b = folder / "b.jpg"
    b.write_text("y")

    plan1 = create_plan(
        [(FileItem(path=a), "Images", "r"), (FileItem(path=b), "Images", "r")],
        folder,
    )
    ids = [op.operation_id for op in plan1]
    assert len(ids) == len(set(ids))
    assert all(len(i) == 12 for i in ids)
