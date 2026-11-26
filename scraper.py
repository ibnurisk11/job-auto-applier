"""Helper HTTP dan I/O yang dipakai bersama oleh semua scraper.

Modul ini sengaja hanya berisi infrastruktur: session, retry, penulisan file,
dan konversi DataFrame. Scraper Jobstreet sudah dihapus karena situsnya
mengembalikan HTTP 403 dan kodenya tidak dipakai lagi.
"""

import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests

from schema import CURRENCY_SYMBOL, COLUMNS, relative_date  # re-export untuk kompatibilitas

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

_respect_robots = False
_robots_cache = {}


class ScraperError(Exception):
    pass


def slugify(keyword):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", keyword.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def set_respect_robots(enabled):
    """Aktifkan/nonaktifkan pengecekan robots.txt (opt-in, lihat README)."""
    global _respect_robots
    _respect_robots = bool(enabled)
    _robots_cache.clear()


def _robot_allowed(session, url):
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    parser = _robots_cache.get(origin)
    if parser is None:
        parser = RobotFileParser()
        parser.set_url(origin + "/robots.txt")
        try:
            response = session.get(origin + "/robots.txt", timeout=10)
            parser.parse(response.text.splitlines())
        except Exception as exc:
            # Tidak bisa membaca robots.txt -> izinkan, tapi beri tahu pengguna.
            print(f"   ⚠️ robots.txt tidak dapat dibaca ({origin}): {exc}", flush=True)
        _robots_cache[origin] = parser
    return parser.can_fetch(HEADERS["User-Agent"], url)


def _retry_after_seconds(response, attempt, rate_limited=False):
    """Ambil jeda dari header Retry-After; ada batas aman 120 detik."""
    header = (response.headers.get("Retry-After") if response is not None else None)
    if header:
        try:
            return min(max(float(header), 0.0), 120.0)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(header)
                delta = (retry_at - datetime.now(timezone.utc)).total_seconds()
                return min(max(delta, 0.0), 120.0)
            except (TypeError, ValueError):
                pass
    return 10.0 * attempt if rate_limited else 2.0 * attempt


def _new_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _safe_get(session, url, params=None, retries=3, timeout=30):
    """GET dengan retry terbatas; 4xx (kecuali 429) tidak di-retry."""
    if _respect_robots:
        full_url = requests.Request("GET", url, params=params).prepare().url
        if not _robot_allowed(session, full_url):
            raise ScraperError(f"Ditolak robots.txt: {full_url}")

    status = None
    response = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            status = response.status_code
            if status == 200:
                return response.text
            # 404/403/... tidak akan membaik dengan retry.
            if 400 <= status < 500 and status != 429:
                break
        except requests.RequestException:
            pass
        if attempt < retries:
            time.sleep(
                _retry_after_seconds(
                    response if status == 429 else None,
                    attempt,
                    rate_limited=(status == 429),
                )
            )

    if status == 403:
        raise ScraperError(f"Akses diblokir situs (HTTP 403): {url}")
    if status == 429:
        raise ScraperError(f"Rate limit terkena (HTTP 429): {url}")
    suffix = f" (HTTP {status})" if status else ""
    raise ScraperError(f"Gagal mengambil halaman{suffix}: {url}")


def to_dataframe(jobs):
    """Paksa urutan kolom stabil walaupun ada scraper yang kehilangan field."""
    normalized = []
    for job in jobs:
        row = {column: "" for column in COLUMNS}
        row.update({key: value for key, value in job.items() if key in COLUMNS})
        normalized.append(row)
    return pd.DataFrame(normalized, columns=COLUMNS)


def _ensure_parent(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def save_csv(df, path):
    """utf-8-sig supaya Excel Windows mengenali judul non-ASCII."""
    _ensure_parent(path)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def save_xlsx(df, path):
    _ensure_parent(path)
    df.to_excel(path, index=False)
    return path


def save_json(df, path):
    _ensure_parent(path)
    df.to_json(path, orient="records", force_ascii=False, indent=2)
    return path
