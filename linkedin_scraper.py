import re
import time

from bs4 import BeautifulSoup

from base_scraper import run_scrape
from schema import empty_job, parse_posted_text
from scraper import ScraperError, _new_session, _safe_get

SOURCE = "LinkedIn"

# Endpoint guest: kartu lowongan tanpa perlu sesi login.
SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs/view/{job_id}"

WORK_TYPE_MAP = {
    "penuh waktu": "Full time",
    "full-time": "Full time",
    "full time": "Full time",
    "paruh waktu": "Part time",
    "part-time": "Part time",
    "kontrak": "Contract",
    "contract": "Contract",
    "magang": "Internship",
    "internship": "Internship",
    "sukarelawan": "Volunteer",
    "volunteer": "Volunteer",
    "lainnya": "Other",
    "other": "Other",
}


def _map_work_type(value):
    if not value:
        return ""
    key = str(value).strip().lower()
    return WORK_TYPE_MAP.get(key, str(value).strip())


def _parse_cards(html, keyword):
    """Parse kartu guest; ID numerik berasal dari ``data-entity-urn``."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.select("div.base-search-card"):
        urn = card.get("data-entity-urn") or ""
        match = re.search(r"(\d+)$", urn)
        if not match:
            continue
        job_id = match.group(1)

        title_el = card.select_one(".base-search-card__title")
        title = title_el.get_text(strip=True) if title_el else ""

        link_el = card.select_one("a.base-card__full-link")
        url = link_el.get("href") if link_el else DETAIL_URL.format(job_id=job_id)
        url = (url or "").split("?")[0].rstrip("/")

        company_el = card.select_one(".base-search-card__subtitle a")
        company = company_el.get_text(strip=True) if company_el else ""

        location_el = card.select_one(".job-search-card__location")
        location = location_el.get_text(strip=True) if location_el else ""

        date_el = card.select_one(".job-search-card__listdate")
        posted = date_el.get_text(strip=True) if date_el else ""

        job = empty_job(SOURCE, keyword)
        job.update(
            {
                "job_id": job_id,
                "title": title,
                "url": url,
                "company": company,
                "location": location,
                "posted_date": posted,
                "posted_at": parse_posted_text(posted),
            }
        )
        jobs.append(job)
    return jobs


def search_jobs(
    keyword,
    location="Indonesia",
    max_pages=3,
    delay=1.0,
    session=None,
    on_progress=None,
    max_jobs=None,
):
    session = session or _new_session()
    keyword = keyword.strip()
    seen = set()
    results = []
    start = 0

    for page in range(1, max_pages + 1):
        params = {"keywords": keyword, "location": location, "start": start}
        url = SEARCH_URL
        if on_progress:
            on_progress("search", page, max_pages, url)
        try:
            html = _safe_get(session, url, params=params)
        except ScraperError:
            # Halaman pertama gagal = sumber benar-benar bermasalah; laporkan.
            if page == 1:
                raise
            break
        page_jobs = _parse_cards(html, keyword)
        if not page_jobs:
            break
        # Guest API mengembalikan jumlah kartu yang berubah-ubah.
        start += len(page_jobs)
        new_jobs = [job for job in page_jobs if job["job_id"] not in seen]
        for job in new_jobs:
            seen.add(job["job_id"])
        results.extend(new_jobs)
        if max_jobs and len(results) >= max_jobs:
            return results[:max_jobs]
        if page < max_pages:
            time.sleep(delay)

    return results


def get_job_detail(job, session=None, retries=2):
    """Perkaya kartu; setiap selector bersifat opsional."""
    session = session or _new_session()
    url = DETAIL_URL.format(job_id=job["job_id"])
    try:
        html = _safe_get(session, url, retries=retries)
    except ScraperError:
        return job

    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1.top-card-layout__title")
    if title_el:
        job["title"] = title_el.get_text(strip=True)

    company_el = soup.select_one("a.topcard__org-name-link")
    if company_el:
        job["company"] = company_el.get_text(strip=True)

    flavor = None
    for item in soup.select(".topcard__flavor"):
        if item.select(".topcard__org-name-link"):
            continue
        text = item.get_text(strip=True)
        if text and "ago" not in text.lower() and "lalu" not in text.lower():
            flavor = item
            break
    if flavor is None:
        flavor = soup.select_one(".topcard__flavor")
    if flavor is not None:
        text = flavor.get_text(strip=True)
        if text:
            job["location"] = text

    date_el = soup.select_one(".posted-time-ago__text")
    if date_el:
        posted = date_el.get_text(strip=True)
        job["posted_date"] = posted
        job["posted_at"] = parse_posted_text(posted)

    desc_el = soup.select_one("div.show-more-less-html__markup")
    if desc_el:
        job["description"] = desc_el.get_text("\n", strip=True)

    # "Employment type" bisa lokal ("Jenis pekerjaan").
    criteria = {}
    for item in soup.select("li.description__job-criteria-item"):
        header = item.select_one(".description__job-criteria-subheader")
        text = item.select_one(".description__job-criteria-text")
        if header and text:
            criteria[header.get_text(strip=True).lower()] = text.get_text(strip=True)

    for key in ("jenis pekerjaan", "employment type"):
        if key in criteria:
            job["work_type"] = _map_work_type(criteria[key])
            break

    return job


def scrape(
    keyword,
    location="Indonesia",
    max_pages=3,
    delay=1.0,
    max_jobs=None,
    on_progress=None,
):
    if on_progress:
        on_progress("search", 0, max_pages, "")

    def search(session, on_progress):
        return search_jobs(
            keyword,
            location,
            max_pages,
            delay,
            session=session,
            on_progress=on_progress,
            max_jobs=max_jobs,
        )

    return run_scrape(
        search_fn=search,
        enrich_fn=get_job_detail,
        session=_new_session(),
        delay=delay,
        max_jobs=max_jobs,
        on_progress=on_progress,
    )
