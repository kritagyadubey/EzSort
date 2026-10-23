"""The version string is defined once and mirrored in shipped metadata."""

from __future__ import annotations

import re
from pathlib import Path

from ezsort import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_version_matches_package() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None, "pyproject.toml has no project version"
    assert match.group(1) == __version__


def test_version_is_three_numeric_parts() -> None:
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_readme_names_the_current_desktop_version() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"## Desktop App (v{__version__})" in text
