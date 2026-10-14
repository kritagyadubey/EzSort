# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the EzSort command-line executable (console).

Build:  pyinstaller packaging/ezsort-cli.spec --noconfirm
Output: dist/ezsort/ezsort.exe
"""

import pathlib

SPEC_DIR = pathlib.Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent

a = Analysis(
    [str(ROOT / "ezsort" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ezsort",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=str(SPEC_DIR / "ezsort.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    # Must differ from the GUI's "EzSort" folder: Windows paths are
    # case-insensitive, so "ezsort" would collide and overwrite it.
    name="ezsort-cli",
)
