"""Shared helper for the PyInstaller specs.

Reads the single source of truth for the version (``ezsort/__init__.py``)
and renders a VSVersionInfo file so Windows Explorer / Task Manager show
the real product name, version and author instead of PyInstaller defaults.

PyInstaller only injects ``SPECPATH`` into the spec file itself, so the
spec passes its directory in explicitly.
"""

from __future__ import annotations

import ast
import pathlib


def read_version(root: pathlib.Path) -> tuple[int, int, int, int]:
    """Parse ``__version__`` from ezsort/__init__.py without importing it."""
    init = pathlib.Path(root) / "ezsort" / "__init__.py"
    tree = ast.parse(init.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    parts = str(ast.literal_eval(node.value)).split(".")
                    nums = [int(p) for p in parts[:4] if p.isdigit()]
                    nums += [0] * (4 - len(nums))
                    return tuple(nums)  # type: ignore[return-value]
    raise RuntimeError(f"__version__ not found in {init}")


def write_version_info(spec_dir, product: str, filename: str) -> str:
    """Write a VSVersionInfo file for *product* and return its path."""
    spec_dir = pathlib.Path(spec_dir).resolve()
    root = spec_dir.parent
    major, minor, patch, build = read_version(root)
    quad = f"({major}, {minor}, {patch}, {build})"
    dotted = f"{major}.{minor}.{patch}.{build}"
    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={quad},
    prodvers={quad},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Kritagya Dubey'),
         StringStruct('FileDescription', '{product}'),
         StringStruct('FileVersion', '{dotted}'),
         StringStruct('InternalName', '{product}'),
         StringStruct('OriginalFilename', '{filename}'),
         StringStruct('ProductName', '{product}'),
         StringStruct('ProductVersion', '{dotted}')])]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    out = root / "build" / f"{product}-version.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return str(out)
