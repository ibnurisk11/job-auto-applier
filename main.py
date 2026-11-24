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
import scraper
import techinasia_scraper
from html_report import render_html

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

SOURCE_NAMES = ["Jobstreet", "Glints", "LinkedIn", "Tech in Asia"]
DEFAULTS = {
    "keyword": "data analyst",
    "sources": ["Glints", "LinkedIn", "Tech in Asia"],
    "location": "Remote",
    "max_pages": 3,
    "delay": 1.0,
    "max_jobs": 0,
}


def load_config(path):
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
    parser.add_argument("--sources", nargs="+", metavar="SOURCE", help="Sumber: Jobstreet Glints LinkedIn 'Tech in Asia'")
    parser.add_argument("--location", help="Lokasi untuk LinkedIn dan Tech in Asia")
    parser.add_argument("--pages", "--max-pages", dest="max_pages", type=int, help="Jumlah halaman")
    parser.add_argument("--delay", type=float, help="Jeda antar request dalam detik")
    parser.add_argument("--max-jobs", type=int, help="Batas job per sumber (0 = semua)")
    return parser.parse_args()


def resolve_settings(args):
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
        canonical = source_lookup.get(name.lower())
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

    return {
        "keyword": str(settings["keyword"]).strip(),
        "sources": sources,
        "location": str(settings.get("location") or "Indonesia").strip() or "Indonesia",
        "max_pages": max_pages,
        "delay": delay,
        "max_jobs": max_jobs,
    }


def console_progress(stage, current, total, label=""):
    if stage == "search":
        print(f"  Mencari lowongan: halaman {current}/{total}", flush=True)
    elif stage == "detail":
        print(f"  Detail {current}/{total}: {label[:70]}", flush=True)


def scrape_source(source, keyword, settings):
    limit = settings["max_jobs"] or None
    if source == "Jobstreet":
        return scraper.scrape(
            keyword,
            max_pages=settings["max_pages"],
            delay=settings["delay"],
            max_jobs=limit,
            on_progress=console_progress,
        )
    if source == "Glints":
        return glints_scraper.scrape(
            keyword,
            delay=settings["delay"],
            max_jobs=limit,
            on_progress=console_progress,
        )
    if source == "LinkedIn":
        return linkedin_scraper.scrape(
            keyword,
            location=settings["location"],
            max_pages=settings["max_pages"],
            delay=settings["delay"],
            max_jobs=limit,
            on_progress=console_progress,
        )
    return techinasia_scraper.scrape(
        keyword,
        location=settings["location"],
        max_pages=settings["max_pages"],
        delay=settings["delay"],
        max_jobs=limit,
        on_progress=console_progress,
    )


def run_scrape(settings):
    all_jobs = []
    for source in settings["sources"]:
        print(f"▶️  Scraping dari {source}...", flush=True)
        try:
            jobs = scrape_source(source, settings["keyword"], settings)
        except scraper.ScraperError as exc:
            print(f"   Gagal scraping {source}: {exc}", flush=True)
            continue
        except Exception as exc:
            print(f"   Error tak terduga saat scraping {source}: {type(exc).__name__}: {exc}", flush=True)
            continue
        print(f"   {source}: {len(jobs)} lowongan", flush=True)
        all_jobs.extend(jobs)

    if not all_jobs:
        return None
    return scraper.to_dataframe(all_jobs)


def save_output(df, keyword, stamp):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_name = f"{scraper.slugify(keyword) or 'jobs'}_{stamp}"
    scraper.save_csv(df, os.path.join(OUTPUT_DIR, f"{base_name}.csv"))
    scraper.save_xlsx(df, os.path.join(OUTPUT_DIR, f"{base_name}.xlsx"))
    df.to_json(
        os.path.join(OUTPUT_DIR, f"{base_name}.json"),
        orient="records",
        force_ascii=False,
        indent=2,
    )
    return base_name


def main():
    args = parse_args()
    try:
        settings = resolve_settings(args)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    print(
        f"Mencari '{settings['keyword']}' dari {', '.join(settings['sources'])} "
        f"(lokasi: {settings['location']}, halaman: {settings['max_pages']}, jeda: {settings['delay']}s)"
    )

    df = run_scrape(settings)
    if df is None:
        print("Tidak ada lowongan ditemukan.")
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_at = datetime.now().strftime("%d %b %Y %H:%M:%S")
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
        },
    )

    print(f"\nSelesai! {len(df)} lowongan berhasil diambil.")
    print(f"Buka laporan di browser: {html_path}")
    print(f"File lain: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
