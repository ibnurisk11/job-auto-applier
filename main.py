"""Command-line entry point: scrape jobs and generate a standalone HTML report.

Usage:
    python main.py
    python main.py --keyword "python" --sources glints linkedin --pages 2 --max-jobs 10

Defaults are read from config.json next to this file; command-line flags override them.
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Windows consoles often default to cp1252, which cannot print emoji or some
# job titles. Recreate the streams as UTF-8 when supported (Python 3.7+).
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

import glints_scraper
import linkedin_scraper
import schema
import scraper
import techinasia_scraper
from html_report import render_html

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

SOURCE_NAMES = ["Glints", "LinkedIn", "Tech in Asia"]
SCRAPERS = {
    "Glints": glints_scraper.scrape,
    "LinkedIn": linkedin_scraper.scrape,
    "Tech in Asia": techinasia_scraper.scrape,
}
UNSUPPORTED_SOURCES = {
    "jobstreet": (
        "Jobstreet sedang tidak didukung (HTTP 403). "
        "Pilih: Glints, LinkedIn, Tech in Asia."
    )
}
DEFAULTS = {
    "keyword": "web developer",
    "sources": ["Glints", "LinkedIn", "Tech in Asia"],
    "location": "Bandung",
    "max_pages": 5,
    "delay": 1.0,
    "max_jobs": 0,
    "respect_robots": False,
    "algolia_app_id": "",
    "algolia_api_key": "",
}


def load_config(path):
    """Load known defaults from JSON; unknown keys are ignored on purpose."""
    config = dict(DEFAULTS)
    if not os.path.exists(path):
        return config
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Peringatan: gagal membaca {path}: {exc}")
        return config
    if not isinstance(data, dict):
        print(f"Peringatan: isi {path} bukan objek JSON, memakai nilai default.")
        return config
    # Only copy recognized keys so a stale/typo key cannot silently change behavior.
    for key in DEFAULTS:
        if key in data:
            config[key] = data[key]
    return config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape lowongan kerja dan simpan hasilnya sebagai HTML, CSV, Excel, dan JSON."
    )
    parser.add_argument("--config", default=CONFIG_PATH, help="Path ke file konfigurasi JSON")
    parser.add_argument("--keyword", help="Posisi / skill yang dicari")
    parser.add_argument("--sources", nargs="+", metavar="SOURCE", help="Sumber: Glints LinkedIn 'Tech in Asia'")
    parser.add_argument("--location", help="Lokasi untuk Glints, LinkedIn, dan Tech in Asia")
    parser.add_argument("--pages", "--max-pages", dest="max_pages", type=int, help="Jumlah halaman")
    parser.add_argument("--delay", type=float, help="Jeda antar request dalam detik")
    parser.add_argument("--max-jobs", type=int, help="Batas job per sumber (0 = semua)")
    parser.add_argument(
        "--respect-robots",
        action="store_true",
        help="Lewati URL yang dilarang robots.txt (opt-in; bisa memblokir sebagian sumber)",
    )
    parser.add_argument("--algolia-app-id", help="Override Algolia app ID untuk Tech in Asia")
    parser.add_argument("--algolia-api-key", help="Override Algolia API key untuk Tech in Asia")
    return parser.parse_args()


def resolve_settings(args):
    """Merge file config + CLI overrides, then validate before any network call."""
    settings = load_config(args.config)
    overrides = {
        "keyword": args.keyword,
        "sources": args.sources,
        "location": args.location,
        "max_pages": args.max_pages,
        "delay": args.delay,
        "max_jobs": args.max_jobs,
    }
    for key, value in overrides.items():
        if value is not None:
            settings[key] = value

    if not str(settings.get("keyword", "")).strip():
        raise ValueError("keyword tidak boleh kosong.")

    source_lookup = {name.lower(): name for name in SOURCE_NAMES}
    raw_sources = settings.get("sources") or []
    if isinstance(raw_sources, str):
        raw_sources = [raw_sources]
    sources = []
    for item in raw_sources:
        name = str(item).strip()
        if not name:
            continue
        lowered = name.lower()
        # Fail early with a specific message instead of sending traffic to a blocked site.
        if lowered in UNSUPPORTED_SOURCES:
            raise ValueError(UNSUPPORTED_SOURCES[lowered])
        canonical = source_lookup.get(lowered)
        if canonical is None:
            raise ValueError(f"Sumber '{name}' tidak dikenal. Pilihan: {', '.join(SOURCE_NAMES)}")
        if canonical not in sources:
            sources.append(canonical)
    if not sources:
        raise ValueError("Pilih minimal satu sumber data.")

    try:
        max_pages = max(1, int(settings.get("max_pages", 3)))
        delay = max(0.0, float(settings.get("delay", 1.0)))
        max_jobs = max(0, int(settings.get("max_jobs", 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Nilai max_pages / delay / max_jobs tidak valid: {exc}") from exc

    # getattr keeps older callers/tests (with a smaller Namespace) working.
    respect_robots = bool(
        getattr(args, "respect_robots", False) or settings.get("respect_robots", False)
    )
    app_id = (
        getattr(args, "algolia_app_id", None)
        or os.environ.get("TECHINASIA_ALGOLIA_APP_ID")
        or str(settings.get("algolia_app_id") or "")
    )
    api_key = (
        getattr(args, "algolia_api_key", None)
        or os.environ.get("TECHINASIA_ALGOLIA_API_KEY")
        or str(settings.get("algolia_api_key") or "")
    )

    return {
        "keyword": str(settings["keyword"]).strip(),
        "sources": sources,
        "location": str(settings.get("location") or "Indonesia").strip() or "Indonesia",
        "max_pages": max_pages,
        "delay": delay,
        "max_jobs": max_jobs,
        "respect_robots": respect_robots,
        "algolia_app_id": app_id,
        "algolia_api_key": api_key,
    }


def console_progress(stage, current, total, label=""):
    if stage == "search":
        print(f"  Mencari lowongan: halaman {current}/{total}", flush=True)
    elif stage == "detail":
        print(f"  Detail {current}/{total}: {label[:70]}", flush=True)


def scrape_source(source, keyword, settings):
    kwargs = {
        "keyword": keyword,
        "location": settings["location"],
        "max_pages": settings["max_pages"],
        "delay": settings["delay"],
        "max_jobs": settings["max_jobs"] or None,
        "on_progress": console_progress,
    }
    if source == "Tech in Asia":
        kwargs["app_id"] = settings.get("algolia_app_id") or None
        kwargs["api_key"] = settings.get("algolia_api_key") or None
    return SCRAPERS[source](**kwargs)


def dedupe_jobs(jobs):
    """Gabungkan lowongan yang sama lintas sumber; simpan sumber lain di ``also_on``."""
    merged = {}
    order = []
    for job in jobs:
        fingerprint = schema.job_fingerprint(job)
        if not any(fingerprint):
            order.append(job)
            continue
        existing = merged.get(fingerprint)
        if existing is None:
            merged[fingerprint] = job
            order.append(job)
            continue

        for column in schema.COLUMNS:
            if not existing.get(column) and job.get(column):
                existing[column] = job[column]

        others = []
        for value in (job.get("source"), existing.get("also_on")):
            for part in str(value or "").split(","):
                part = part.strip()
                if part and part != existing.get("source") and part not in others:
                    others.append(part)
        existing["also_on"] = ", ".join(others)
    return order


def run_scrape(settings):
    """Scrape tiap sumber secara independen; kegagalan satu tidak menghentikan lain."""
    all_jobs = []
    issues = []
    for source in settings["sources"]:
        print(f"▶️  Scraping dari {source}...", flush=True)
        try:
            jobs = scrape_source(source, settings["keyword"], settings)
        except scraper.ScraperError as exc:
            message = str(exc)
            print(f"   Gagal scraping {source}: {message}", flush=True)
            issues.append({"source": source, "kind": "error", "message": message})
            continue
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            print(f"   Error tak terduga saat scraping {source}: {message}", flush=True)
            issues.append({"source": source, "kind": "error", "message": message})
            continue

        if not jobs:
            issues.append({"source": source, "kind": "empty", "message": "0 lowongan"})
            print(
                f"   ⚠️ {source}: 0 lowongan — tidak ada hasil atau struktur/API berubah.",
                flush=True,
            )
        else:
            print(f"   {source}: {len(jobs)} lowongan", flush=True)
        all_jobs.extend(jobs)

    if not all_jobs:
        return None, issues
    return scraper.to_dataframe(dedupe_jobs(all_jobs)), issues


def save_output(df, keyword, stamp):
    """Tulis CSV/XLSX/JSON dengan basename berTimestamp yang sama."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_name = f"{scraper.slugify(keyword) or 'jobs'}_{stamp}"
    scraper.save_csv(df, os.path.join(OUTPUT_DIR, f"{base_name}.csv"))
    scraper.save_xlsx(df, os.path.join(OUTPUT_DIR, f"{base_name}.xlsx"))
    scraper.save_json(df, os.path.join(OUTPUT_DIR, f"{base_name}.json"))
    return base_name


def build_notes(issues):
    """Bedakan 'sumber gagal' dari 'sumber sukses tapi kosong' di laporan."""
    notes = []
    for issue in issues:
        if issue["kind"] == "error":
            notes.append(f"{issue['source']}: gagal scraping — {issue['message']}")
        else:
            notes.append(
                f"{issue['source']}: 0 lowongan (tidak ada hasil atau struktur/API berubah)"
            )
    return notes


def main():
    args = parse_args()
    try:
        settings = resolve_settings(args)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    scraper.set_respect_robots(settings["respect_robots"])
    print(
        f"Mencari '{settings['keyword']}' dari {', '.join(settings['sources'])} "
        f"(lokasi: {settings['location']}, halaman: {settings['max_pages']}, jeda: {settings['delay']}s)"
    )

    df, issues = run_scrape(settings)
    if df is None:
        print("Tidak ada lowongan ditemukan.")
        return 1

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    generated_at = now.strftime("%d %b %Y %H:%M:%S")
    base_name = save_output(df, settings["keyword"], stamp)
    html_path = os.path.join(OUTPUT_DIR, f"{base_name}.html")
    render_html(
        df,
        html_path,
        base_name,
        meta={
            "keyword": settings["keyword"],
            "sources": settings["sources"],
            "location": settings["location"],
            "generated_at": generated_at,
            "notes": build_notes(issues),
        },
    )

    print(f"\nSelesai! {len(df)} lowongan berhasil diambil.")
    print(f"Buka laporan di browser: {html_path}")
    print(f"File lain: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
