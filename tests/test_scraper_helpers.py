import pytest

import scraper
from schema import job_fingerprint, parse_posted_text, relative_date, salary_info
from datetime import datetime, timedelta, timezone


class _Response:
    def __init__(self, status, text="", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        return self.responses.pop(0)


def test_salary_info_menghasilkan_string_dan_angka():
    info = salary_info(6000000, 8000000, "IDR", "month")
    assert info["salary"] == "Rp 6,000,000 - Rp 8,000,000 per month"
    assert info["salary_min"] == 6000000.0
    assert info["salary_max"] == 8000000.0
    assert info["currency"] == "IDR"
    assert info["salary_period"] == "month"


def test_relative_date_dan_posted_text():
    now = datetime.now(timezone.utc)
    assert relative_date(now - timedelta(days=3)) == "Posted 3d ago"
    assert parse_posted_text("3d ago", now=now) == (
        now - timedelta(days=3)
    ).isoformat(timespec="seconds")
    assert parse_posted_text("bukan tanggal") == ""


def test_fingerprint_menyamakan_judul_yang_sedikit_beda():
    a = {"title": "Data Analyst", "company": "Acme, Inc.", "location": "Bandung"}
    b = {"title": "data  analyst", "company": "ACME Inc", "location": " bandung "}
    assert job_fingerprint(a) == job_fingerprint(b)


def test_safe_get_retry_lima_ratus_tidak_retry_empat_ratus(monkeypatch):
    sleeps = []
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: sleeps.append(seconds))

    session = _Session([_Response(500), _Response(200, "ok")])
    assert scraper._safe_get(session, "https://example.com") == "ok"
    assert len(session.calls) == 2
    assert sleeps == [2.0]

    session = _Session([_Response(404)])
    with pytest.raises(scraper.ScraperError, match="HTTP 404"):
        scraper._safe_get(session, "https://example.com")
    assert len(session.calls) == 1


def test_safe_get_mematuhi_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: sleeps.append(seconds))
    session = _Session(
        [_Response(429, headers={"Retry-After": "1"}), _Response(200, "ok")]
    )
    assert scraper._safe_get(session, "https://example.com") == "ok"
    assert sleeps == [1.0]


def test_robots_opt_in_menolak_path_yang_dilarang():
    robots = _Response(200, "User-agent: *\nDisallow: /private\n")
    session = _Session([robots])
    scraper.set_respect_robots(True)
    try:
        with pytest.raises(scraper.ScraperError, match="robots.txt"):
            scraper._safe_get(session, "https://example.com/private")
    finally:
        scraper.set_respect_robots(False)
