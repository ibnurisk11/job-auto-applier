import pytest

import linkedin_scraper
from scraper import ScraperError

CARD_HTML = """
<div class="base-search-card" data-entity-urn="urn:li:fsd_jobPosting:12345">
  <h3 class="base-search-card__title">Data Analyst</h3>
  <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/12345/?tracking=1">link</a>
  <h4 class="base-search-card__subtitle"><a href="#">Acme</a></h4>
  <span class="job-search-card__location">Bandung, Jawa Barat</span>
  <time class="job-search-card__listdate">3d ago</time>
</div>
"""


def test_parse_kartu_mengisi_field_dan_posted_at():
    jobs = linkedin_scraper._parse_cards(CARD_HTML, "data analyst")
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_id"] == "12345"
    assert job["url"] == "https://www.linkedin.com/jobs/view/12345"
    assert job["company"] == "Acme"
    assert job["location"] == "Bandung, Jawa Barat"
    assert job["posted_date"] == "3d ago"
    assert job["posted_at"]


def test_error_halaman_pertama_tidak_lagi_ditelan(monkeypatch):
    def boom(*args, **kwargs):
        raise ScraperError("Rate limit terkena (HTTP 999)")

    monkeypatch.setattr(linkedin_scraper, "_safe_get", boom)
    with pytest.raises(ScraperError, match="HTTP 999"):
        linkedin_scraper.search_jobs("python", max_pages=1)


def test_max_jobs_menghentikan_pencarian_lebih_awal(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return "<html></html>"

    monkeypatch.setattr(linkedin_scraper, "_safe_get", fake_get)
    monkeypatch.setattr(
        linkedin_scraper,
        "_parse_cards",
        lambda html, keyword: [
            {"job_id": str(index), "title": f"Job {index}"} for index in range(3)
        ],
    )
    jobs = linkedin_scraper.search_jobs("python", max_pages=5, max_jobs=2)
    assert len(jobs) == 2
    assert len(calls) == 1
