# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the EzSort command-line executable (console).

Build:  pyinstaller packaging/ezsort-cli.spec --noconfirm
Output: dist/ezsort-cli/ezsort.exe
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
VERSION_FILE = _version_info.write_version_info(SPEC_DIR, "EzSort", "ezsort.exe")

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
    version=VERSION_FILE,
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
