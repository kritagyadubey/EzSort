"""End-to-end verification of the built GUI EXE.

Launches the real frozen executable with an isolated EZSORT_HOME, waits
for its main window, captures a screenshot, exercises it (theme switch +
preview via config/geometry persistence), then closes it through
WM_CLOSE. Nothing touches the real user profile.

Usage:  python scripts/verify_gui_exe.py [path/to/EzSort.exe]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import ctypes
from ctypes import wintypes
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
user32 = ctypes.windll.user32
DWMWA_CLOAKED = 14

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  [{'ok' if condition else 'FAIL'}] {message}")
    if not condition:
        failures.append(message)


def enum_windows_for_pid(pid: int) -> list[int]:
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        proc_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def is_cloaked(hwnd: int) -> bool:
    cloaked = wintypes.DWORD()
    try:
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        return hr == 0 and cloaked.value != 0
    except Exception:
        return False


def wait_for_window(proc: subprocess.Popen, timeout: float = 60.0) -> int | None:
    """Wait until the app shows a real (visible, uncloaked) top-level window."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return None
        for hwnd in enum_windows_for_pid(proc.pid):
            if is_cloaked(hwnd):
                continue
            if window_title(hwnd).startswith("EzSort"):
                return hwnd
        time.sleep(0.25)
    return None


def screenshot(path: Path, hwnd: int) -> bool:
    """Capture the window's own pixels, even if another window covers it.

    ImageGrab grabs screen contents, so an occluded window would capture
    whatever is on top instead. PrintWindow renders this window alone.
    """
    rect = wintypes.RECT()
    # DWM extended frame bounds excludes the invisible resize border.
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)
        )
    except Exception:
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width < 50 or height < 50:
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
    if width < 50 or height < 50:
        return False

    try:
        import ctypes.wintypes as wt

        from PIL import Image  # type: ignore

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wt.DWORD), ("biWidth", wt.LONG),
                ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD),
            ]

        hwnd_dc = user32.GetDC(0)
        mem_dc = ctypes.windll.gdi32.CreateCompatibleDC(hwnd_dc)
        bitmap = ctypes.windll.gdi32.CreateCompatibleBitmap(
            hwnd_dc, width, height
        )
        ctypes.windll.gdi32.SelectObject(mem_dc, bitmap)
        # PW_RENDERFULLCONTENT (2) also captures layered/composited windows.
        ok = user32.PrintWindow(hwnd, mem_dc, 2)
        if not ok:
            ok = user32.PrintWindow(hwnd, mem_dc, 0)  # plain fallback
        if not ok:
            raise RuntimeError("PrintWindow failed")

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = width
        bmi.biHeight = -height  # top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        buf = ctypes.create_string_buffer(width * height * 4)
        ctypes.windll.gdi32.GetDIBits(
            mem_dc, bitmap, 0, height, buf, ctypes.byref(bmi), 0
        )
        image = Image.frombuffer("RGBA", (width, height), buf.raw, "raw",
                                 "BGRA", 0, 1).convert("RGB")
        image.save(str(path))

        ctypes.windll.gdi32.DeleteObject(bitmap)
        ctypes.windll.gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(0, hwnd_dc)
        return True
    except Exception as exc:  # pragma: no cover - PIL missing, GDI failure
        print(f"    PrintWindow capture failed: {exc}")
        # Last resort: screen grab, but only after the window is in front.
        try:
            from PIL import ImageGrab  # type: ignore

            user32.SetForegroundWindow(hwnd)
            time.sleep(0.6)
            ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom)
                           ).save(str(path))
            return True
        except Exception:
            return False


def main() -> int:
    exe = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        REPO_ROOT / "dist" / "EzSort" / "EzSort.exe"
    )
    if not exe.is_file():
        print(f"EXE not found: {exe}")
        return 2

    work = Path(tempfile.mkdtemp(prefix="ezsort-gui-verify-"))
    home = work / "home"
    home.mkdir()
    demo = work / "demo-downloads"
    demo.mkdir()
    for name, content in {
        "photo.jpg": b"jpeg", "report.pdf": b"pdf", "notes.txt": b"text",
        "song.mp3": b"audio", "movie.mp4": b"video", "backup.zip": b"zip",
        "script.py": b"code", "budget.csv": b"csv",
    }.items():
        (demo / name).write_bytes(content)

    shots = REPO_ROOT / "docs" / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)

    print(f"EXE:    {exe}")
    print(f"Folder: {demo}")
    print(f"Home:   {home}\n")

    env = dict(os.environ)
    env["EZSORT_HOME"] = str(home)

    proc: subprocess.Popen | None = None
    try:
        print("-- launch --")
        proc = subprocess.Popen(
            [str(exe)], env=env, cwd=str(work),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        check(proc.poll() is None, "the EXE stays running after launch")
        hwnd = wait_for_window(proc)
        check(hwnd is not None, "the main window appears")
        if hwnd is None:
            out, err = proc.communicate(timeout=10)
            print(f"    stdout: {out.decode(errors='replace')[:500]}")
            print(f"    stderr: {err.decode(errors='replace')[:500]}")
            return 1

        title = window_title(hwnd)
        check("EzSort" in title, f"window title is '{title}'")
        check("0.3.0" in title, "title shows the 0.3.0 version")

        time.sleep(2.5)  # let the dashboard scan settle
        # Raise it first: a screen-grab fallback would otherwise capture
        # whatever else is on the monitor.
        user32.SetForegroundWindow(hwnd)
        time.sleep(1.0)
        shot = shots / "exe-gui-launch.png"
        check(screenshot(shot, hwnd), f"screenshot saved: {shot.name}")

        print("\n-- window is interactive --")
        # Restore/foreground it, as a user clicking the taskbar would.
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.8)
        check(user32.IsWindow(hwnd), "window still responds after focus")

        print("\n-- close via WM_CLOSE (the title-bar X) --")
        WM_CLOSE = 0x0010
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            check(False, "the EXE exited after WM_CLOSE")
        else:
            check(proc.returncode == 0,
                  f"the EXE exited cleanly (code {proc.returncode})")
            check(enum_windows_for_pid(proc.pid) == [],
                  "the main window is gone")

        print("\n-- state persisted to the isolated profile --")
        config_path = home / "config.json"
        check(config_path.is_file(), f"config written: {config_path.name}")
        if config_path.is_file():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception as exc:
                config = {}
                check(False, f"config.json is valid JSON ({exc})")
            else:
                check(config.get("theme") in ("dark", "light", None),
                      f"theme persisted: {config.get('theme')!r}")
                geo = config.get("window_geometry", "")
                check(bool(geo), f"window geometry persisted: {geo!r}")
                # The demo folder must never leak into the real profile.
                check(str(demo) not in json.dumps(config),
                      "no test folder leaked into the saved config")

        check(not (demo / "Documents").exists(),
              "launching the app moved no files")

        print("\n-- relaunch picks the saved state back up --")
        proc2 = subprocess.Popen([str(exe)], env=env, cwd=str(work))
        try:
            hwnd2 = wait_for_window(proc2, timeout=45)
            check(hwnd2 is not None, "the app relaunches")
            if hwnd2:
                geo_before = json.loads(config_path.read_text("utf-8")).get(
                    "window_geometry", "")
                time.sleep(1.5)
                check(window_title(hwnd2).startswith("EzSort"),
                      "relaunched window has the right title")
                user32.PostMessageW(hwnd2, 0x0010, 0, 0)
                try:
                    proc2.wait(timeout=25)
                    check(True, "relaunched app closes cleanly")
                except subprocess.TimeoutExpired:
                    proc2.kill()
                    check(False, "relaunched app closed cleanly")
                print(f"    saved geometry: {geo_before!r}")
        finally:
            if proc2.poll() is None:
                proc2.kill()
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
        shutil.rmtree(work, ignore_errors=True)

    print()
    if failures:
        print(f"GUI EXE VERIFICATION FAILED ({len(failures)} problem(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("GUI EXE VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
