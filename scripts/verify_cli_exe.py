"""End-to-end verification of the built CLI EXE on a throwaway folder.

Nothing here touches real user files: every path is inside a fresh
%TEMP% directory that is deleted afterwards.

Usage:  python scripts/verify_cli_exe.py [path/to/ezsort.exe]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEMO_FILES = {
    "photo.jpg": b"jpeg",
    "holiday.png": b"png",
    "report.pdf": b"pdf",
    "notes.txt": b"text",
    "song.mp3": b"audio",
    "movie.mp4": b"video",
    "backup.zip": b"zip",
    "script.py": b"code",
    "budget.csv": b"csv",
    "näme with ünicode.pdf": b"unicode",
    "archive.tar.gz": b"gz",
    "leftover.crdownload": b"partial",
    ".hidden.jpg": b"hidden",
}

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  [{'ok' if condition else 'FAIL'}] {message}")
    if not condition:
        failures.append(message)


def run(exe: Path, args: list[str], home: Path, cwd: Path):
    env = dict(os.environ)
    env["EZSORT_HOME"] = str(home)
    return subprocess.run(
        [str(exe), *args],
        capture_output=True, text=True, timeout=120,
        env=env, cwd=str(cwd),
    )


def main() -> int:
    exe = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        REPO_ROOT / "dist" / "ezsort-cli" / "ezsort.exe"
    )
    if not exe.is_file():
        print(f"EXE not found: {exe}")
        return 2

    work = Path(tempfile.mkdtemp(prefix="ezsort-cli-verify-"))
    home = work / "home"
    home.mkdir()
    demo = work / "demo-downloads"
    demo.mkdir()
    for name, content in DEMO_FILES.items():
        (demo / name).write_bytes(content)

    print(f"EXE:     {exe}")
    print(f"Folder:  {demo}")
    print(f"Home:    {home}\n")

    try:
        print("-- version --")
        proc = run(exe, ["--version"], home, work)
        check(proc.returncode == 0, f"--version exits 0 (got {proc.returncode})")
        check("0.3.0" in proc.stdout, f"version string shows 0.3.0: {proc.stdout.strip()!r}")

        print("\n-- scan (no side effects) --")
        before = sorted(p.name for p in demo.iterdir())
        proc = run(exe, ["scan", str(demo)], home, work)
        out = proc.stdout + proc.stderr
        check(proc.returncode == 0, f"scan exits 0 (got {proc.returncode})")
        # 'scan' prints a summary report (counts by category), not a
        # filename listing - so assert on the report's own vocabulary.
        check("Files found" in out, "scan prints its report header")
        check("Organizable files" in out, "scan reports organizable files")
        check("Images" in out and "Documents" in out,
              "scan names the categories it found")
        after = sorted(p.name for p in demo.iterdir())
        check(before == after, "scan moved nothing")

        print("\n-- organize --dry-run --")
        proc = run(exe, ["organize", str(demo), "--dry-run"], home, work)
        check(proc.returncode == 0, f"dry-run exits 0 (got {proc.returncode})")
        after = sorted(p.name for p in demo.iterdir())
        check(before == after, "dry-run moved nothing")
        check(not (demo / "Documents").exists(), "dry-run created no folders")

        print("\n-- organize (real) --")
        proc = run(exe, ["organize", str(demo), "--yes"], home, work)
        out = proc.stdout + proc.stderr
        check(proc.returncode == 0, f"organize exits 0 (got {proc.returncode})")
        check((demo / "Images" / "photo.jpg").exists(), "photo.jpg -> Images")
        check((demo / "Images" / "holiday.png").exists(), "holiday.png -> Images")
        check((demo / "Documents" / "report.pdf").exists(), "report.pdf -> Documents")
        check((demo / "Documents" / "näme with ünicode.pdf").exists(),
              "unicode filename handled")
        check((demo / "Archives" / "archive.tar.gz").exists(),
              "compound extension -> Archives")
        check((demo / "Music" / "song.mp3").exists(), "song.mp3 -> Music")
        check((demo / "Videos" / "movie.mp4").exists(), "movie.mp4 -> Videos")
        check((demo / "Code" / "script.py").exists(), "script.py -> Code")
        check((demo / "leftover.crdownload").exists(),
              "partial download left untouched")
        check(not (demo / "photo.jpg").exists(), "original photo.jpg removed")
        print("    output preview: " + out.strip().splitlines()[0][:90]
              if out.strip() else "    (no output)")

        print("\n-- history --")
        proc = run(exe, ["history"], home, work)
        check(proc.returncode == 0, f"history exits 0 (got {proc.returncode})")
        check("001" in proc.stdout or "1" in proc.stdout,
              "history lists the batch")

        print("\n-- stats --")
        proc = run(exe, ["stats"], home, work)
        check(proc.returncode == 0, f"stats exits 0 (got {proc.returncode})")

        print("\n-- undo --")
        proc = run(exe, ["undo"], home, work)
        check(proc.returncode == 0, f"undo exits 0 (got {proc.returncode})")
        check((demo / "photo.jpg").exists(), "undo restored photo.jpg")
        check((demo / "report.pdf").exists(), "undo restored report.pdf")
        check((demo / "song.mp3").exists(), "undo restored song.mp3")
        check(not (demo / "Images" / "photo.jpg").exists(),
              "undo removed the moved copy")
        check((demo / "leftover.crdownload").exists(),
              "partial download still untouched after undo")

        print("\n-- undo with nothing left --")
        proc = run(exe, ["undo"], home, work)
        check("no operations" in (proc.stdout + proc.stderr).lower()
              or proc.returncode != 0,
              "second undo reports there is nothing to undo")

        print("\n-- config --")
        proc = run(exe, ["config"], home, work)
        check(proc.returncode == 0, f"config exits 0 (got {proc.returncode})")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if failures:
        print(f"CLI EXE VERIFICATION FAILED ({len(failures)} problem(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("CLI EXE VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
