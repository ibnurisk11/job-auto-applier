import argparse
import os

import main
import schema
from scraper import ScraperError


def _settings(sources):
    return {
        "keyword": "python",
        "sources": sources,
        "location": "Bandung",
        "max_pages": 1,
        "delay": 0.0,
        "max_jobs": 0,
    }


def test_gagal_vs_kosong_dibedakan_dalam_catatan(monkeypatch):
    def fake_scrape(source, keyword, settings):
        if source == "LinkedIn":
            raise ScraperError("Rate limit terkena (HTTP 999)")
        return []

    monkeypatch.setattr(main, "scrape_source", fake_scrape)
    df, issues = main.run_scrape(_settings(["LinkedIn", "Glints"]))

    assert df is None
    assert [issue["kind"] for issue in issues] == ["error", "empty"]
    notes = main.build_notes(issues)
    assert "LinkedIn: gagal scraping — Rate limit" in notes[0]
    assert "Glints: 0 lowongan" in notes[1]


def test_dedup_lintas_sumber_menyimpan_sumber_lain():
    def job(source, title="Data Analyst"):
        row = schema.empty_job(source, "python")
        row.update({"job_id": "1", "title": title, "company": "Acme", "location": "Bandung"})
        return row

    jobs = main.dedupe_jobs([job("Glints"), job("LinkedIn")])
    assert len(jobs) == 1
    assert jobs[0]["source"] == "Glints"
    assert jobs[0]["also_on"] == "LinkedIn"


def test_resolve_settings_menerima_namespace_lama():
    args = argparse.Namespace(
        config="config.json",
        keyword="python",
        sources=["Glints"],
        location=None,
        max_pages=None,
        delay=None,
        max_jobs=None,
    )
    settings = main.resolve_settings(args)
    assert settings["sources"] == ["Glints"]
    assert settings["respect_robots"] is False
    assert settings["algolia_api_key"] == os.environ.get(
        "TECHINASIA_ALGOLIA_API_KEY", ""
    )
