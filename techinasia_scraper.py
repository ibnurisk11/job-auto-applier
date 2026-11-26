import json
import os
import platform
import re
import time
from datetime import datetime
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from base_scraper import run_scrape
from schema import empty_job, relative_date, salary_info
from scraper import ScraperError, _new_session

SOURCE = "Tech in Asia"

ALGOLIA_URL = "https://219wx3mpv4-dsn.algolia.net/1/indexes/*/queries"
# Kunci pencarian publik milik frontend Tech in Asia (bukan kredensial privat).
# Selalu bisa ditimpa lewat env var atau argumen CLI; lihat README.
DEFAULT_APP_ID = "219WX3MPV4"
DEFAULT_API_KEY = "b528008a75dc1c4402bfe0d8db8b3f8e"
APP_ID = os.environ.get("TECHINASIA_ALGOLIA_APP_ID", DEFAULT_APP_ID)
API_KEY = os.environ.get("TECHINASIA_ALGOLIA_API_KEY", DEFAULT_API_KEY)
INDEX_NAME = "job_postings"
AGENT = f"job-auto-applier/1.0; Python {platform.python_version()}"

DETAIL_URL = "https://www.techinasia.com/jobs/{job_id}"

WORK_TYPE_MAP = {
    "Full-time": "Full time",
    "Full time": "Full time",
    "Part-time": "Part time",
    "Part time": "Part time",
    "Contract": "Contract",
    "Freelance": "Freelance",
    "Internship": "Internship",
    "Temporary": "Temporary",
}


def resolve_credentials(app_id=None, api_key=None):
    """Prioritas: argumen CLI > environment variable > kunci publik bawaan."""
    return (
        app_id or os.environ.get("TECHINASIA_ALGOLIA_APP_ID") or APP_ID,
        api_key or os.environ.get("TECHINASIA_ALGOLIA_API_KEY") or API_KEY,
    )


def _algolia_params(keyword, location, page, hits_per_page=100):
    """Bangun query Algolia; lokasi adalah facet exact, jadi ejaan harus cocok."""
    params = {
        "query": keyword,
        "hitsPerPage": hits_per_page,
        "page": page,
    }
    if location.strip():
        facet = f"city.work_country_name:{location.strip()}"
        params["facetFilters"] = json.dumps([[facet]])
    return urlencode(params)


def _safe_post(session, url, body, params=None, retries=3, timeout=30):
    """POST dengan retry terbatas dan pesan error yang menyebut HTTP status."""
    status = None
    for attempt in range(1, retries + 1):
        try:
            response = session.post(url, params=params, json=body, timeout=timeout)
            status = response.status_code
            if status == 200:
                return response.json()
            if 400 <= status < 500 and status != 429:
                break
        except (requests.RequestException, ValueError):
            pass
        if attempt < retries:
            time.sleep(10.0 * attempt if status == 429 else 2.0 * attempt)
    suffix = f" (HTTP {status})" if status else ""
    raise ScraperError(f"Gagal mengambil data Tech in Asia{suffix}")


def _salary_fields(hit):
    if not hit.get("is_salary_visible"):
        return {}
    currency = (hit.get("currency") or {}).get("currency_code")
    return salary_info(hit.get("salary_min"), hit.get("salary_max"), currency)


def _posted(raw):
    """Kembalikan (tampilan relatif, ISO absolut) dari ``published_at``."""
    if not raw:
        return "", ""
    try:
        created = datetime.strptime(str(raw).strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "", ""
    return relative_date(created), created.isoformat(timespec="seconds")


def _strip_html(value):
    if not value:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _map_work_type(value):
    if not value:
        return ""
    return WORK_TYPE_MAP.get(str(value).strip(), str(value).strip())


def _extract_skills(hit):
    skills = hit.get("job_skills") or []
    names = [
        str(skill.get("name"))
        for skill in skills
        if isinstance(skill, dict) and skill.get("name")
    ]
    return ", ".join(names)


def _map_job(hit, keyword):
    """Hit Algolia sudah berisi deskripsi & skill; tidak perlu request detail."""
    city = hit.get("city") or {}
    location = ", ".join(
        part for part in (city.get("name"), city.get("country_name")) if part
    )
    company = (hit.get("company") or {}).get("name") or ""
    job_id = str(hit.get("id") or hit.get("objectID") or "")
    posted_text, posted_at = _posted(hit.get("published_at"))

    job = empty_job(SOURCE, keyword)
    job.update(
        {
            "job_id": job_id,
            "title": hit.get("title") or "",
            "url": DETAIL_URL.format(job_id=job_id),
            "company": company,
            "location": location,
            "work_type": _map_work_type((hit.get("job_type") or {}).get("name")),
            "posted_date": posted_text,
            "posted_at": posted_at,
            "description": _strip_html(hit.get("description")),
            "skills": _extract_skills(hit),
        }
    )
    job.update(_salary_fields(hit))
    return job


def search_jobs(
    keyword,
    location="",
    max_pages=3,
    delay=1.0,
    session=None,
    on_progress=None,
    max_jobs=None,
    app_id=None,
    api_key=None,
):
    session = session or _new_session()
    keyword = keyword.strip()
    resolved_app, resolved_key = resolve_credentials(app_id, api_key)
    seen = set()
    results = []

    for page in range(max_pages):
        if on_progress:
            on_progress("search", page + 1, max_pages, ALGOLIA_URL)
        body = {
            "requests": [
                {
                    "indexName": INDEX_NAME,
                    "params": _algolia_params(keyword, location, page),
                }
            ]
        }
        params = {
            "x-algolia-application-id": resolved_app,
            "x-algolia-api-key": resolved_key,
            "x-algolia-agent": AGENT,
        }
        data = _safe_post(session, ALGOLIA_URL, body, params=params)
        hits = (data.get("results") or [{}])[0].get("hits") or []
        if not hits:
            break

        for hit in hits:
            job = _map_job(hit, keyword)
            if not job["job_id"] or job["job_id"] in seen:
                continue
            seen.add(job["job_id"])
            results.append(job)
            if max_jobs and len(results) >= max_jobs:
                break
        if max_jobs and len(results) >= max_jobs:
            break
        if page < max_pages - 1:
            time.sleep(delay)

    return results


def scrape(
    keyword,
    location="",
    max_pages=3,
    delay=1.0,
    max_jobs=None,
    on_progress=None,
    app_id=None,
    api_key=None,
):
    # Peringatan dipindah ke sini agar tidak muncul saat sumber lain dipilih.
    if (api_key or resolve_credentials()[1]) == DEFAULT_API_KEY:
        print(
            "   ⚠️ Tech in Asia: Algolia API key default digunakan; "
            "set TECHINASIA_ALGOLIA_API_KEY untuk override.",
            flush=True,
        )

    def search(session, on_progress):
        return search_jobs(
            keyword,
            location,
            max_pages,
            delay,
            session=session,
            on_progress=on_progress,
            max_jobs=max_jobs,
            app_id=app_id,
            api_key=api_key,
        )

    return run_scrape(
        search_fn=search,
        session=_new_session(),
        delay=delay,
        max_jobs=max_jobs,
        on_progress=on_progress,
    )
