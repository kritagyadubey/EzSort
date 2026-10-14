"""Tests for the engine facade (preview + execution) used by CLI and GUI."""

from __future__ import annotations

from pathlib import Path

from ezsort import engine


def make_messy_folder(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.jpg").write_bytes(b"img")
    (root / "b.pdf").write_bytes(b"pdf")
    (root / "c.mp3").write_bytes(b"mp3")
    (root / "partial.crdownload").write_bytes(b"dl")
    (root / "install.part").write_bytes(b"part")
    (root / "secret.xyz").write_bytes(b"unknown")


def test_build_preview_counts_and_skips(tmp_path):
    folder = tmp_path / "mess"
    make_messy_folder(folder)
    config = engine.load_config()

    preview = engine.build_preview(folder, config=config)

    names = [f.path.name for f in preview.files]
    # partial downloads filtered out by the engine
    assert "partial.crdownload" not in names
    assert "install.part" not in names
    # 4 remaining files are all planned
    assert preview.ready == 4
    assert preview.categories["Images"] == 1
    assert preview.errors == []
    assert preview.total_size > 0


def test_preview_does_not_touch_files(tmp_path):
    folder = tmp_path / "mess"
    make_messy_folder(folder)
    engine.build_preview(folder, config=engine.load_config())
    assert (folder / "a.jpg").exists()
    assert not (folder / "Images").exists()


def test_run_plan_moves_and_records(tmp_path):
    folder = tmp_path / "mess"
    make_messy_folder(folder)
    preview = engine.build_preview(folder, config=engine.load_config())
    summary = engine.run_plan(preview, dry_run=False)

    assert summary.moved == 4
    assert summary.failed == 0
    assert (folder / "Images" / "a.jpg").exists()
    assert (folder / "Documents" / "b.pdf").exists()

    history = engine.load_history()
    assert len(history) == 1
    assert history[0]["total_moved"] == 4
    assert history[0]["folder"] == str(folder)


def test_run_plan_dry_run_records_nothing(tmp_path):
    folder = tmp_path / "mess"
    make_messy_folder(folder)
    preview = engine.build_preview(folder, config=engine.load_config())
    summary = engine.run_plan(preview, dry_run=True)
    assert summary.moved == 4
    assert summary.batch_id == ""
    assert engine.load_history() == []
    assert (folder / "a.jpg").exists()


def test_run_plan_duplicate_strategy_skip(tmp_path):
    folder = tmp_path / "dups"
    folder.mkdir()
    (folder / "one.jpg").write_bytes(b"original")
    (folder / "Images").mkdir()
    (folder / "Images" / "one.jpg").write_bytes(b"already there")

    config = engine.load_config()
    config["duplicate_strategy"] = "skip"
    preview = engine.build_preview(folder, config=config)
    assert preview.ready == 1  # plan shows it...
    summary = engine.run_plan(preview, dry_run=False, config=config)
    # ...but skip strategy does not execute it
    assert summary.moved == 0
    assert len(summary.skipped_duplicates) == 1
    assert (folder / "one.jpg").read_bytes() == b"original"
    assert (folder / "Images" / "one.jpg").read_bytes() == b"already there"


def test_run_plan_progress_and_cancel(tmp_path):
    folder = tmp_path / "many"
    folder.mkdir()
    for i in range(6):
        (folder / f"file{i}.jpg").write_bytes(b"x" * (i + 1))

    preview = engine.build_preview(folder, config=engine.load_config())
    seen = []

    def progress(done, total, op):
        seen.append((done, total))

    # Cancel after two files have been moved.
    summary = engine.run_plan(
        preview, dry_run=False, progress=progress,
        cancel_check=lambda: len(seen) >= 2,
    )
    assert summary.moved == 2
    assert summary.cancelled is True
    assert len(seen) == 2

    # The remaining files complete in a second, uncancelled run.
    preview2 = engine.build_preview(folder, config=engine.load_config())
    summary2 = engine.run_plan(
        preview2, dry_run=False, progress=progress,
        cancel_check=lambda: False,
    )
    assert summary2.moved == 4
    assert summary2.cancelled is False
    assert len(seen) == 6
    assert seen[-1] == (4, 4)


def test_organize_folder_convenience(tmp_path):
    folder = tmp_path / "one"
    folder.mkdir()
    (folder / "x.png").write_bytes(b"png")
    preview, summary = engine.organize_folder(
        folder, config=engine.load_config(), dry_run=False
    )
    assert summary.moved == 1
    assert (folder / "Images" / "x.png").exists()


def test_history_stats_and_drop(tmp_path):
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "y.txt").write_bytes(b"t")
    engine.organize_folder(folder, config=engine.load_config(), dry_run=False)

    stats = engine.stats()
    assert stats["batches"] == 1
    assert stats["total_moved"] == 1
    assert stats["categories"]["Documents"] == 1

    batch_id = engine.load_history()[0]["batch_id"]
    assert engine.drop_batch(batch_id) is True
    assert engine.drop_batch("nonexistent") is False


def test_undo_specific_batch(tmp_path):
    folder = tmp_path / "u"
    folder.mkdir()
    (folder / "z.docx").write_bytes(b"doc")
    engine.organize_folder(folder, config=engine.load_config(), dry_run=False)
    batch_id = engine.load_history()[0]["batch_id"]

    ok, msg = engine.undo_specific_batch(batch_id)
    assert ok
    assert (folder / "z.docx").exists()
    ok2, _ = engine.undo_specific_batch(batch_id)
    assert not ok2  # already undone / gone
