"""Tests for configuration management."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch
from ezsort.config import (
    load_config, save_config, get_default_config,
    get_config_dir, get_categories, get_excluded_dirs,
    add_custom_rule,
)


def test_get_default_config():
    config = get_default_config()
    assert "categories" in config
    assert "excluded_dirs" in config
    assert "custom_rules" in config
    assert isinstance(config["categories"], dict)


def test_load_config_returns_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: tmp_path / "nonexistent.json")
    config = load_config()
    assert config == get_default_config()


def test_save_and_load_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: config_path)
    
    config = get_default_config()
    config["confirm_before_move"] = False
    save_config(config)
    
    loaded = load_config()
    assert loaded["confirm_before_move"] is False


def test_get_categories():
    config = get_default_config()
    cats = get_categories(config)
    assert "Images" in cats
    assert ".jpg" in cats["Images"]


def test_get_excluded_dirs():
    config = get_default_config()
    dirs = get_excluded_dirs(config)
    assert ".git" in dirs
    assert "node_modules" in dirs


def test_add_custom_rule():
    config = get_default_config()
    config = add_custom_rule(config, "extension", ".psd", "Design")
    assert len(config["custom_rules"]) == 1
    assert config["custom_rules"][0]["category"] == "Design"


def test_config_dir_platform():
    config_dir = get_config_dir()
    assert "ezsort" in str(config_dir).lower()


def test_invalid_json_returns_defaults(monkeypatch, tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not valid json {{{")
    monkeypatch.setattr("ezsort.config.get_config_path", lambda: bad_json)
    config = load_config()
    assert config == get_default_config()
