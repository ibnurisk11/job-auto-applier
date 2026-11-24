import glints_scraper


class _Stop(Exception):
    pass


class _FakeSession:
    headers = {}

    def get(self, url, params=None, timeout=None):
        self.url = url
        self.params = params
        raise _Stop()


def test_search_jobs_includes_location_in_url():
    session = _FakeSession()
    try:
        glints_scraper.search_jobs("data analyst", location="Bandung", session=session)
    except _Stop:
        pass
    assert "keyword=data+analyst" in session.url
    assert "location=Bandung" in session.url


def test_scrape_warns_when_max_pages_above_one(monkeypatch, capsys):
    monkeypatch.setattr(glints_scraper, "search_jobs", lambda *a, **k: [])
    glints_scraper.scrape("data analyst", max_pages=3)
    assert "pagination belum didukung" in capsys.readouterr().out
