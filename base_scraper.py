"""Orkestrasi bersama untuk seluruh scraper.

Tiap scraper hanya perlu menyediakan ``search_fn`` dan ``enrich_fn``; urutan
paging detail, jeda, progress, dan stempel waktu ditangani di satu tempat.
"""

import time
from datetime import datetime

from schema import COLUMNS
from scraper import _new_session


def run_scrape(
    *,
    search_fn,
    enrich_fn=None,
    session=None,
    delay=1.0,
    max_jobs=None,
    on_progress=None,
):
    """Jalankan pencarian lalu pengayaan detail dengan perilaku yang seragam."""
    session = session or _new_session()
    jobs = search_fn(session=session, on_progress=on_progress) or []

    if max_jobs:
        jobs = jobs[:max_jobs]

    total = len(jobs)
    if enrich_fn:
        for index, job in enumerate(jobs, start=1):
            if on_progress:
                on_progress("detail", index, total, job.get("title") or "")
            enrich_fn(job, session=session)
            if index < total:
                time.sleep(delay)

    now = datetime.now().isoformat(timespec="seconds")
    for job in jobs:
        for column in COLUMNS:
            job.setdefault(column, "")
        job["scraped_at"] = now
    return jobs
