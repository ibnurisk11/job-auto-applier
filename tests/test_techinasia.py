import importlib

import techinasia_scraper as module


def test_algolia_key_can_be_overridden(monkeypatch):
    original = module.API_KEY
    monkeypatch.setenv("TECHINASIA_ALGOLIA_API_KEY", "test-key")
    try:
        importlib.reload(module)
        assert module.API_KEY == "test-key"
    finally:
        monkeypatch.delenv("TECHINASIA_ALGOLIA_API_KEY", raising=False)
        importlib.reload(module)
    assert module.API_KEY == original
