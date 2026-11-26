import json
import re
from datetime import datetime
from urllib.parse import urlencode

from base_scraper import run_scrape
from schema import empty_job, relative_date, salary_info
from scraper import ScraperError, _new_session, _safe_get

SOURCE = "Glints"

SEARCH_URL = "https://glints.com/id/opportunities/jobs/explore"
DETAIL_URL = "https://glints.com/id/opportunities/jobs/{slug}/{job_id}"

WORK_TYPE_MAP = {
    "FULL_TIME": "Full time",
    "PART_TIME": "Part time",
    "CONTRACT": "Contract",
    "TEMPORARY": "Temporary",
    "INTERNSHIP": "Internship",
    "VOLUNTEER": "Volunteer",
}


def _next_data(html):
    """Baca payload Next.js ``__NEXT_DATA__`` yang disisipkan server."""
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    if not match:
        return None
    return json.loads(match.group(1))


def _extract_description(desc_json):
    """Terima blok editor.js, string JSON, atau teks biasa."""
    if not desc_json:
        return ""
    if isinstance(desc_json, str):
        try:
            data = json.loads(desc_json)
        except (TypeError, ValueError):
            return desc_json
    else:
        data = desc_json
    if isinstance(data, dict):
        blocks = data.get("blocks") or []
        return "\n".join(
            b.get("text", "")
            for b in blocks
            if isinstance(b, dict) and b.get("text")
        )
    if isinstance(data, list):
        return "\n".join(
            str(b.get("text", "")) if isinstance(b, dict) else str(b)
            for b in data
        )
    return str(data)


def _salary_fields(salaries):
    """Gabungkan beberapa entry gaji menjadi string tampilan + angka."""
    displays = []
    numbers = {}
    for item in salaries or []:
        if not isinstance(item, dict):
            continue
        info = salary_info(
            item.get("minAmount"),
            item.get("maxAmount"),
            item.get("CurrencyCode") or "IDR",
            item.get("salaryMode"),
            default_symbol="Rp",
        )
        if info["salary"]:
            displays.append(info["salary"])
            if not numbers:
                numbers = {key: value for key, value in info.items() if key != "salary"}
    result = {"salary": "; ".join(displays)}
    result.update(
        {
            "salary_min": "",
            "salary_max": "",
            "currency": "",
            "salary_period": "",
        }
    )
    result.update(numbers)
    return result


def _posted(raw):
    """Kembalikan (tampilan relatif, ISO absolut) dari ``createdAt``."""
    if not raw:
        return "", ""
    try:
        created = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
    except ValueError:
        return "", ""
    return relative_date(created), created.isoformat(timespec="seconds")


def _map_work_type(value):
    if not value:
        return ""
    return WORK_TYPE_MAP.get(str(value).upper(), str(value).replace("_", " ").title())


def _extract_skills(raw):
    skills = raw.get("skills") or raw.get("JobSkills")
    if not skills:
        return ""
    names = []
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        if isinstance(skill.get("skill"), dict):
            name = skill["skill"].get("name")
        else:
            name = skill.get("name") or skill.get("skillName")
        if name:
            names.append(str(name))
    return ", ".join(names)


def _map_job(raw, keyword):
    location = ""
    place = raw.get("location")
    if isinstance(place, dict) and place.get("formattedName"):
        location = place["formattedName"]

    company = ""
    org = raw.get("company")
    if isinstance(org, dict):
        company = org.get("name") or ""

    posted_text, posted_at = _posted(raw.get("createdAt"))
    job = empty_job(SOURCE, keyword)
    job.update(
        {
            "job_id": str(raw.get("id", "")),
            "title": raw.get("title") or "",
            "company": company,
            "location": location,
            "work_type": _map_work_type(raw.get("type")),
            "posted_date": posted_text,
            "posted_at": posted_at,
            "skills": _extract_skills(raw),
        }
    )
    job.update(_salary_fields(raw.get("salaries")))
    return job


def _slug_map(html):
    """Kumpulkan slug dari href server-rendered; API hanya memberi ID."""
    hrefs = re.findall(
        r'href="(/id/opportunities/jobs/([^/"]+)/'
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}))",
        html,
    )
    return {job_id: slug for _, slug, job_id in hrefs}


def search_jobs(keyword, location="", session=None, on_progress=None, max_jobs=None):
    """Ambil halaman pertama hasil Glints (API explore tidak menyediakan paging)."""
    session = session or _new_session()
    keyword = keyword.strip()
    params = {"keyword": keyword}
    if location and location.strip():
        params["location"] = location.strip()
    url = f"{SEARCH_URL}?{urlencode(params)}"
    if on_progress:
        on_progress("search", 1, 1, url)
    html = _safe_get(session, url)
    data = _next_data(html)
    if not data:
        return []
    initial = data.get("props", {}).get("pageProps", {}).get("initialJobs") or {}
    raw_jobs = initial.get("jobsInPage") or []
    if max_jobs:
        raw_jobs = raw_jobs[:max_jobs]
    slugs = _slug_map(html)

    jobs = []
    for raw in raw_jobs:
        job = _map_job(raw, keyword)
        job_id = job["job_id"]
        slug = slugs.get(job_id)
        if slug:
            job["url"] = DETAIL_URL.format(slug=slug, job_id=job_id)
        else:
            job["url"] = f"https://glints.com/id/opportunities/jobs/{job_id}"
        jobs.append(job)
    return jobs


def get_job_detail(job, session=None, retries=2):
    session = session or _new_session()
    url = job.get("url")
    if not url:
        return job
    try:
        html = _safe_get(session, url, retries=retries)
    except ScraperError:
        return job

    data = _next_data(html)
    if not data:
        return job
    raw = (
        data.get("props", {})
        .get("pageProps", {})
        .get("initialData", {})
        .get("data")
        or {}
    )
    if not raw:
        return job

    if raw.get("title"):
        job["title"] = raw["title"]
    company = raw.get("company") or {}
    if isinstance(company, dict) and company.get("name"):
        job["company"] = company["name"]
    if raw.get("descriptionJsonString"):
        job["description"] = _extract_description(raw["descriptionJsonString"])
    if raw.get("type"):
        job["work_type"] = _map_work_type(raw["type"])
    if raw.get("createdAt"):
        posted_text, posted_at = _posted(raw["createdAt"])
        if posted_text:
            job["posted_date"] = posted_text
        if posted_at:
            job["posted_at"] = posted_at
    salary = _salary_fields(raw.get("salaries"))
    if salary["salary"]:
        job.update(salary)
    skills = _extract_skills(raw)
    if skills:
        job["skills"] = skills

    return job


def scrape(keyword, location="", max_pages=1, delay=1.0, max_jobs=None, on_progress=None):
    # Diterima agar config konsisten; beri peringatan instead of diam-diam diabaikan.
    if max_pages and max_pages > 1:
        print(
            "   ⚠️ Glints: pagination belum didukung, hanya mengambil 1 halaman.",
            flush=True,
        )

    def search(session, on_progress):
        return search_jobs(
            keyword,
            location,
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
