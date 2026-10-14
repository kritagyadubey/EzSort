"""Shared test fixtures.

Every test runs with EZSORT_HOME pointed at a temporary directory, so no
test can ever read or write the real user configuration/history files.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_ezsort_home(tmp_path, monkeypatch):
    """Redirect config + history into a throwaway folder per test."""
    home = tmp_path / "ezsort-home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("EZSORT_HOME", str(home))
    return home
