"""Capture real EzSort window screenshots for docs and UX reviews.

This is a development tool, never part of the shipped app. It runs the real
Tk application against a throwaway ``EZSORT_HOME`` and a synthetic demo
folder (fake filenames only), so screenshots never contain personal data.

Usage:
    python scripts/capture_ui.py --out docs/_baseline
    python scripts/capture_ui.py --out docs/screenshots --theme both
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEMO_FILES = [
    "quarterly-report.pdf", "meeting-notes.txt", "invoice-2026-014.pdf",
    "beach-sunset.jpg", "team-photo.png", "product-mockup.psd",
    "budget-forecast.xlsx", "sales-data.csv", "launch-deck.pptx",
    "onboarding.mp4", "demo-recording.mov", "podcast-intro.mp3",
    "playlist-backup.m4a", "release-notes.md", "archive-old-site.zip",
    "project-source.tar.gz", "EzSort-setup.exe", "mobile-build.apk",
    "app-config.json", "theme-overrides.css", "utility-script.py",
    "custom-font.woff2", "design-system.epub", "linux-image.iso",
    "notes-final-FINAL-v3.txt",
    "a-very-long-client-project-name-for-the-north-region-rollout-2026.pdf",
]


def build_demo_tree(base: Path) -> Path:
    """Create a realistic but entirely synthetic folder of files."""
    demo = base / "Sample Downloads"
    demo.mkdir(parents=True, exist_ok=True)
    for name in DEMO_FILES:
        path = demo / name
        path.write_bytes(f"synthetic demo content for {name}".encode("utf-8"))
    # A couple of already-organized folders so scans show real structure.
    for folder in ("Images", "Documents", "Projects/Archive"):
        (demo / folder).mkdir(parents=True, exist_ok=True)
    (demo / "Projects/Archive/old-brief.txt").write_text(
        "synthetic archive note", encoding="utf-8"
    )
    return demo


def prepare_profile(base: Path) -> Path:
    """Create an isolated config profile with a couple of custom rules."""
    home = base / "ezsort-home"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["EZSORT_HOME"] = str(home)

    from ezsort.config import get_default_config, save_config

    config = get_default_config()
    config["theme"] = "dark"
    config["confirm_before_move"] = True
    config["custom_rules"] = [
        {"type": "filename_contains", "pattern": "invoice",
         "category": "Documents", "subfolder": "Invoices"},
        {"type": "extension", "pattern": ".psd",
         "category": "Design", "subfolder": ""},
    ]
    save_config(config)
    return home


def _grab(root, out: Path) -> None:
    from PIL import ImageGrab

    # Park the OS cursor on the desktop: leaving it over the title bar can
    # pop the Windows 11 snap-layout flyout into the screenshot.
    try:
        import ctypes

        ctypes.windll.user32.SetCursorPos(4, 4)
    except Exception:
        pass
    root.update_idletasks()
    root.update()
    time.sleep(0.65)
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    image = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
    image.save(out)
    print(f"  [grab] root={root.geometry()} winfo={root.winfo_width()}x{root.winfo_height()} "
          f"status_y={root.winfo_rooty() + root.winfo_height() - 25}")
    print(f"wrote {out} ({w}x{h})")


def _pump(root, rounds: int = 8) -> None:
    for _ in range(rounds):
        root.update()
        root.update_idletasks()
        time.sleep(0.01)


def capture(out_dir: Path, themes: list[str], width: int, height: int) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="ezsort-capture-"))
    demo = build_demo_tree(temp_root)
    prepare_profile(temp_root)

    from ezsort import engine
    from ezsort.gui.app import EzSortApp
    from ezsort.gui.theme import apply_styles

    # Real sorts on synthetic copies, so History/Activity show real data.
    run_dir = temp_root / "Run One"
    run_dir.mkdir()
    for name in ("holiday-photo.jpg", "tax-return-2025.pdf", "voice-memo.m4a",
                 "installer-notes.txt"):
        (run_dir / name).write_bytes(b"demo")
    second_dir = temp_root / "Run Two"
    second_dir.mkdir()
    for name in ("sprint-plan.xlsx", "logo-draft.png", "soundtrack.mp3"):
        (second_dir / name).write_bytes(b"demo")

    app = EzSortApp()
    # Map the window first: Windows ignores a position set before the first
    # map and cascades the window instead.
    app.root.update()
    app.root.geometry(f"{width}x{height}+24+24")
    app.root.update()
    app.root.attributes("-topmost", True)
    app.config["confirm_before_move"] = False
    app.folder = demo
    _pump(app.root)

    for folder in (run_dir, second_dir):
        preview = engine.build_preview(folder, config=app.config, recursive=False)
        engine.run_plan(preview, config=app.config)
    app.log({"type": "info", "message": "Preview completed for Sample Downloads"})
    app.log({"type": "moved", "message": "Moved 24 files into 9 categories"})
    app.log({"type": "info", "message": "Watch mode is idle"})

    pages = ["dashboard", "organizer", "categories", "history", "activity",
             "settings"]
    written = 0
    for theme_name in themes:
        app.update_config(theme=theme_name, quiet=True)
        app.apply_theme(theme_name)
        settings_page = app.pages.get("settings")
        if settings_page is not None:
            settings_page.sync_from_config()
        _pump(app.root)
        for page_name in pages:
            app.root.attributes("-topmost", True)
            app.show_page(page_name)
            page = app.pages[page_name]
            _pump(app.root)
            if page_name == "organizer":
                preview = engine.build_preview(demo, config=app.config,
                                               recursive=False)
                app.folder = demo
                page.set_folder(demo)
                page.preview = preview
                page._populate(preview)
                _pump(app.root)
            if page_name == "dashboard":
                preview = engine.build_preview(demo, config=app.config,
                                               recursive=False)
                page._render(preview)
                _pump(app.root)
            if page_name == "history":
                page.refresh()
                _pump(app.root)
                children = page.batch_tree.get_children()
                if children:
                    page.batch_tree.selection_set(children[0])
                    page._on_batch_select()
                _pump(app.root)
            if page_name == "activity":
                page.render_all()
                _pump(app.root)
            if page_name == "settings":
                page.sync_from_config()
            suffix = "-light" if theme_name == "light" else ""
            target = out_dir / f"{page_name}{suffix}.png"
            app.toast_host.hide()
            from ezsort.gui.components import ToolTip

            if ToolTip._active is not None:
                ToolTip._active._hide()
            _grab(app.root, target)
            written += 1

    app.root.attributes("-topmost", False)
    app.runner.close()
    app.root.destroy()
    print(f"captured {written} screenshots from synthetic data in {demo}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/_baseline")
    parser.add_argument("--theme", choices=["dark", "light", "both"],
                        default="both")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=940)
    args = parser.parse_args()
    themes = ["dark", "light"] if args.theme == "both" else [args.theme]
    return capture(ROOT / args.out, themes, args.width, args.height)


if __name__ == "__main__":
    sys.exit(main())
