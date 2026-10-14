"""Headless-ish GUI smoke test: drives the real Tk interface end-to-end.

Usage:  python scripts/gui_smoke.py

Creates a demo folder, opens the app, visits every page, previews, sorts,
undoes and verifies the files really moved. Exits non-zero on failure.
Screenshots are written to docs/screenshots/.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Isolate config/history before importing ezsort pieces.
WORKDIR = Path(tempfile.mkdtemp(prefix="ezsort-gui-smoke-"))
os.environ["EZSORT_HOME"] = str(WORKDIR / "home")

DEMO = WORKDIR / "demo-downloads"
SCREENSHOTS = REPO_ROOT / "docs" / "screenshots"


def build_demo_folder() -> None:
    if DEMO.exists():
        shutil.rmtree(DEMO, ignore_ok=True)
    DEMO.mkdir(parents=True)
    files = {
        "photo.jpg": b"jpeg",
        "holiday.png": b"png",
        "report.pdf": b"pdf",
        "notes.txt": b"text",
        "song.mp3": b"audio",
        "movie.mp4": b"video",
        "backup.zip": b"zip",
        "setup.exe": b"exe",
        "script.py": b"code",
        "budget.csv": b"csv",
        "slides.pptx": b"ppt",
        "näme with ünicode.pdf": b"unicode",
        "archive.tar.gz": b"gz",
        "big.file.name.with.dots.docx": b"dots",
        "leftover.crdownload": b"partial",
        ".hidden.jpg": b"hidden",
    }
    for name, content in files.items():
        (DEMO / name).write_bytes(content)


def wait_for(app, predicate, timeout: float = 30.0, label: str = "condition"):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        app.root.update()
        if predicate():
            return
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {label}")


def main() -> int:
    build_demo_folder()
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    from ezsort.gui.app import EzSortApp

    app = EzSortApp()
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        status = "ok" if condition else "FAIL"
        print(f"  [{status}] {message}")
        if not condition:
            failures.append(message)

    try:
        app.root.geometry("1180x760")
        # Every page must construct cleanly.
        for name in ("dashboard", "organizer", "categories", "history",
                     "activity", "settings"):
            app.show_page(name)
            app.root.update()
            check(name in app.pages, f"page '{name}' loads")

        # --- organizer preview ---------------------------------------
        organizer = app.pages["organizer"]
        app.show_page("organizer")
        organizer.set_folder(DEMO)
        app.root.update()
        organizer.preview_folder()
        wait_for(app, lambda: organizer.preview is not None,
                 label="preview completion")
        preview = organizer.preview
        check(preview is not None and preview.ready >= 13,
              f"preview plans moves (ready={preview.ready})")
        check(any("crdownload" in reason for _, reason in preview.skipped),
              "partial download is skipped")
        check(not any(f.path.name == ".hidden.jpg" for f in preview.files),
              "hidden files excluded by default")
        check(organizer.sort_btn.instate(["!disabled"]),
              "Sort button enables after preview")
        app.root.update()
        shot = SCREENSHOTS / "organizer-preview.png"
        _screenshot(shot, app)

        # --- dashboard screenshot -------------------------------------
        app.show_page("dashboard")
        wait_for(app, lambda: app.pages["dashboard"].preview is not None,
                 label="dashboard preview")
        app.root.update()
        shot = SCREENSHOTS / "dashboard.png"
        _screenshot(shot, app)

        # --- sorting (no confirmation dialog) --------------------------
        app.config["confirm_before_move"] = False
        app.show_page("organizer")
        organizer.preview = preview  # reuse the plan built above
        app.root.update()
        organizer.sort_files()
        wait_for(app, lambda: not organizer.running and organizer.preview is None,
                 label="sort completion")

        check((DEMO / "Images" / "photo.jpg").exists(), "photo.jpg moved to Images")
        check((DEMO / "Documents" / "näme with ünicode.pdf").exists(),
              "unicode pdf moved to Documents")
        check((DEMO / "Archives" / "archive.tar.gz").exists(),
              "compound extension moved to Archives")
        check((DEMO / "leftover.crdownload").exists(),
              "partial download left untouched")

        from ezsort import engine

        history = engine.load_history()
        check(len(history) >= 1, "history recorded")

        # --- undo ---------------------------------------------------
        app.show_page("history")
        app.pages["history"].refresh()
        app.root.update()
        engine.undo_last_batch()
        check((DEMO / "report.pdf").exists(), "undo restored report.pdf")
        check(not (DEMO / "Documents" / "report.pdf").exists()
              if (DEMO / "Documents").exists() else True,
              "undo removed the moved copy")

        # --- categories page CRUD ------------------------------------
        app.show_page("categories")
        cats = app.pages["categories"]
        cats.pattern_var.set("special")
        cats.category_var.set("Special")
        cats.add_rule()
        check(len(app.config.get("custom_rules", [])) == 1, "custom rule added")
        children = cats.rule_tree.get_children()
        check(len(children) == 1, "rule appears in the rules table")
        if children:
            cats.rule_tree.selection_set(children[0])
            cats._on_rule_select()
        cats.remove_rule()
        check(len(app.config.get("custom_rules", [])) == 0, "custom rule removed")

        # --- settings + theme switch ---------------------------------
        app.show_page("settings")
        settings = app.pages["settings"]
        settings.theme_var.set("light")
        settings._theme_changed()
        app.root.update()
        check(app.palette["name"] == "light", "light theme applied")
        settings.theme_var.set("dark")
        settings._theme_changed()
        app.root.update()
        check(app.palette["name"] == "dark", "dark theme applied")

        # --- activity log --------------------------------------------
        app.show_page("activity")
        app.root.update()
        check(len(app.activity) > 0, "activity entries recorded")

        # --- settings screenshot -------------------------------------
        app.show_page("settings")
        app.root.update()
        _screenshot(SCREENSHOTS / "settings.png", app)
        app.show_page("history")
        app.root.update()
        _screenshot(SCREENSHOTS / "history.png", app)
        app.show_page("dashboard")
        app.root.update()
        _screenshot(SCREENSHOTS / "dashboard.png", app)

    except Exception:
        traceback.print_exc()
        failures.append("unhandled exception during smoke run")
    finally:
        try:
            app.root.destroy()
        except Exception:
            pass
        shutil.rmtree(WORKDIR, ignore_errors=True)

    print()
    if failures:
        print(f"SMOKE TEST FAILED ({len(failures)} problem(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SMOKE TEST PASSED")
    return 0


def _window_bbox(app) -> tuple[int, int, int, int] | None:
    try:
        root = app.root
        root.lift()
        root.attributes("-topmost", True)
        root.focus_force()
        root.update()
        root.update_idletasks()
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        w = root.winfo_width()
        h = root.winfo_height()
        if w > 1 and h > 1:
            return (x, y, x + w, y + h)
    except Exception:
        pass
    return None


def _screenshot(path: Path, app=None) -> None:
    import time

    bbox = _window_bbox(app) if app is not None else None
    if app is not None:
        time.sleep(0.2)  # let the UI settle after the raise
    try:
        from PIL import ImageGrab  # type: ignore

        if bbox:
            ImageGrab.grab(bbox=bbox).save(str(path))
        else:
            ImageGrab.grab().save(str(path))
        print(f"  screenshot: {path}")
        return
    except Exception:
        pass
    _screenshot_powershell(path, bbox)


def _screenshot_powershell(path: Path, bbox=None) -> None:
    import subprocess

    if bbox:
        x, y, w, h = bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]
        region = (
            f"$rect = New-Object System.Drawing.Rectangle {x},{y},{w},{h}; "
            "$img = New-Object System.Drawing.Bitmap $rect.Width, $rect.Height; "
            "$g = [System.Drawing.Graphics]::FromImage($img); "
            f"$g.CopyFromScreen($rect.Location, [System.Drawing.Point]::Empty, $rect.Size); "
        )
    else:
        region = (
            "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$img = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
            "$g = [System.Drawing.Graphics]::FromImage($img); "
            "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
        )
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        + region
        + f"$img.Save('{path.as_posix()}')"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=True, capture_output=True, timeout=60,
        )
        print(f"  screenshot: {path}")
    except Exception as e:
        print(f"  screenshot failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
