import pandas as pd

from html_report import COLUMNS, render_html


def _row(**overrides):
    row = {column: "" for column in COLUMNS}
    row.update(
        {
            "source": "Glints",
            "keyword": "data analyst",
            "job_id": "1",
            "title": "Data Analyst",
            "url": "https://example.com/job/1",
            "company": "Acme",
            "location": "Bandung",
            "salary": "USD $5,000 - $7,000",
            "description": "Info </script> dan $100",
            "skills": "Python, SQL",
            "scraped_at": "2026-01-01T00:00:00",
        }
    )
    row.update(overrides)
    return row


def test_render_html_keeps_dollar_signs_and_escapes_script_close(tmp_path):
    df = pd.DataFrame([_row()], columns=COLUMNS)
    path = tmp_path / "report.html"
    render_html(
        df,
        path,
        "sample",
        meta={
            "keyword": "C++ $100",
            "sources": ["Glints"],
            "location": "Indonesia",
            "generated_at": "01 Jan 2026 00:00:00",
            "notes": ["Glints: 0 lowongan — kemungkinan struktur berubah."],
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "$5,000" in text
    assert "C++ $100" in text
    assert "<title>Job Scraper - C++ $100</title>" in text
    assert "<\\/script>" in text
    assert "struktur berubah" in text
