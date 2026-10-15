# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the EzSort desktop GUI (windowed, no console).

Build:  pyinstaller packaging/ezsort-gui.spec --noconfirm
Output: dist/EzSort/EzSort.exe
"""

import importlib.util
import pathlib

SPEC_DIR = pathlib.Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent


def _load_version_helper():
    """Import packaging/version_info.py by path (no package install needed)."""
    path = SPEC_DIR / "version_info.py"
    spec = importlib.util.spec_from_file_location("ezsort_version_info", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_version_info = _load_version_helper()
VERSION_FILE = _version_info.write_version_info(SPEC_DIR, "EzSort", "EzSort.exe")

a = Analysis(
    [str(ROOT / "ezsort" / "gui" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    # Bundle the icon as data too: the app looks it up at runtime to set the
    # window/taskbar icon, and frozen builds cannot reach packaging/ on disk.
    datas=[(str(SPEC_DIR / "ezsort.ico"), "packaging")],
    hiddenimports=[
        "ezsort.gui.pages.dashboard",
        "ezsort.gui.pages.organizer",
        "ezsort.gui.pages.categories",
        "ezsort.gui.pages.history",
        "ezsort.gui.pages.activity",
        "ezsort.gui.pages.settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EzSort",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(SPEC_DIR / "ezsort.ico"),
    version=VERSION_FILE,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="EzSort",
)
