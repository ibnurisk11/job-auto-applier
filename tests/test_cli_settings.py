import argparse
import json

import pytest

import main


def _args(config, **overrides):
    values = {
        "config": str(config),
        "keyword": None,
        "sources": None,
        "location": None,
        "max_pages": None,
        "delay": None,
        "max_jobs": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _config(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_jobstreet_is_explicitly_rejected(tmp_path):
    cfg = _config(tmp_path, {"keyword": "data analyst", "sources": ["Jobstreet"]})
    with pytest.raises(ValueError, match="tidak didukung"):
        main.resolve_settings(_args(cfg))


def test_supported_sources_exclude_jobstreet():
    assert "Jobstreet" not in main.SOURCE_NAMES


def test_sources_override_config(tmp_path):
    cfg = _config(tmp_path, {"keyword": "data analyst", "sources": ["Jobstreet"]})
    settings = main.resolve_settings(_args(cfg, sources=["Glints"]))
    assert settings["sources"] == ["Glints"]
