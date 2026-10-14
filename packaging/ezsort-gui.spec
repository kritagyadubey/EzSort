# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the EzSort desktop GUI (windowed, no console).

Build:  pyinstaller packaging/ezsort-gui.spec --noconfirm
Output: dist/EzSort/EzSort.exe
"""

import pathlib

SPEC_DIR = pathlib.Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent

a = Analysis(
    [str(ROOT / "ezsort" / "gui" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
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
