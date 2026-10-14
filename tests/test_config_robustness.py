"""Configuration robustness: env override, merging, corruption recovery."""

from __future__ import annotations

import json

from ezsort import config as cfg


def test_ezsort_home_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("EZSORT_HOME", str(tmp_path / "portable"))
    assert cfg.get_config_dir() == tmp_path / "portable"
    assert cfg.get_config_path() == tmp_path / "portable" / "config.json"
    assert cfg.get_history_path() == tmp_path / "portable" / "history.json"


def test_partial_config_gets_defaults(tmp_path, monkeypatch):
    """A config written by an older version must not crash new code."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"confirm_before_move": False}))
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: path)

    config = cfg.load_config()
    # user value wins...
    assert config["confirm_before_move"] is False
    # ...but missing keys are filled in
    assert config["categories"]  # dict
    assert config["custom_rules"] == []
    assert config["watch_interval"] == 2
    assert config["skip_partial_downloads"] is True


def test_corrupt_config_is_backed_up_not_lost(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("{ this is not json")
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: path)

    config = cfg.load_config()
    assert config == cfg.get_default_config()
    # The unreadable file was preserved for inspection
    assert not path.exists()
    backup = path.with_name("config.json.corrupt")
    assert backup.exists()
    assert "not json" in backup.read_text()


def test_non_object_config_rejected(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(["not", "an", "object"]))
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: path)
    assert cfg.load_config() == cfg.get_default_config()


def test_invalid_value_types_are_repaired(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "watch_interval": "soon",
        "categories": "nope",
        "custom_rules": [{"type": "extension"}, "junk", None],
        "confirm_before_move": "yes",
        "duplicate_strategy": "explode",
    }))
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: path)

    config = cfg.load_config()
    assert config["watch_interval"] == 2
    assert config["categories"]  # fell back to defaults
    assert all(isinstance(r, dict) for r in config["custom_rules"])
    assert config["duplicate_strategy"] == "rename"


def test_save_config_creates_dirs_and_roundtrips(tmp_path, monkeypatch):
    path = tmp_path / "deep" / "nested" / "config.json"
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: path)

    config = cfg.get_default_config()
    config["custom_rules"] = [
        {"type": "extension", "pattern": ".psd", "category": "Design", "subfolder": ""}
    ]
    cfg.save_config(config)
    loaded = cfg.load_config()
    assert loaded["custom_rules"][0]["pattern"] == ".psd"
    # No leftover temporary files from the atomic write
    leftovers = [p.name for p in path.parent.iterdir() if p.name != "config.json"]
    assert leftovers == []


def test_get_categories_defaults_not_aliased():
    """Mutating the returned defaults must not corrupt the module state."""
    from ezsort.constants import DEFAULT_CATEGORIES

    cats = cfg.get_categories(None)
    cats["Images"].append(".evil")
    assert ".evil" not in DEFAULT_CATEGORIES["Images"]


def test_excluded_extensions(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"excluded_extensions": [".LOG", "csv"]}))
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: path)
    config = cfg.load_config()
    exts = cfg.get_excluded_extensions(config)
    assert ".log" in exts
    assert "csv" in exts
