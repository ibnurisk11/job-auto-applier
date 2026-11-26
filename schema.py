"""Skema data dan helper normalisasi yang dipakai bersama oleh semua scraper.

Modul ini adalah satu-satunya sumber kebenaran untuk susunan kolom. Scraper
mengisi field mentah, lalu helper di sini menghasilkan nilai tampilan (string)
dan nilai terstruktur (angka/ISO) yang bisa dipakai untuk filter dan sortir.
"""

import re
from datetime import datetime, timedelta, timezone

CURRENCY_SYMBOL = {
    "IDR": "Rp",
    "SGD": "S$",
    "MYR": "RM",
    "PHP": "₱",
    "THB": "฿",
    "VND": "₫",
    "USD": "$",
    "AUD": "A$",
}

COLUMNS = [
    "source",
    "keyword",
    "job_id",
    "title",
    "url",
    "company",
    "location",
    "salary",
    "salary_min",
    "salary_max",
    "currency",
    "salary_period",
    "work_type",
    "posted_date",
    "posted_at",
    "description",
    "skills",
    "also_on",
    "scraped_at",
]

PERIOD_LABELS = {
    "month": "per month",
    "year": "per year",
    "day": "per day",
    "hour": "per hour",
}

_UNIT_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,
    "year": 31536000,
    "detik": 1,
    "menit": 60,
    "jam": 3600,
    "hari": 86400,
    "minggu": 604800,
    "bulan": 2592000,
    "tahun": 31536000,
    "d": 86400,
    "h": 3600,
    "w": 604800,
    "mo": 2592000,
    "y": 31536000,
}


def empty_job(source="", keyword=""):
    """Buat dict dengan semua kolom terdefinisi (menghindari NaN dari pandas)."""
    job = {column: "" for column in COLUMNS}
    job["source"] = source
    job["keyword"] = keyword
    return job


def to_number(value):
    """Ubah nilai gaji menjadi float, atau '' bila tidak bisa diparse."""
    if value is None or value == "":
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        return ""


def salary_info(low, high, currency=None, period=None, default_symbol=""):
    """Buat string gaji dan field numeriknya.

    ``default_symbol`` dipakai bila payload tidak menyebut mata uang (Glints
    memakai IDR sebagai implisit). Field numerik memungkinkan sortir/filter,
    sementara string ``salary`` tetap dipakai di laporan HTML.
    """
    code = str(currency or "").strip().upper()
    symbol = CURRENCY_SYMBOL.get(code) or code or default_symbol
    amounts = []
    for value in (low, high):
        if value is None or value == "":
            continue
        try:
            amounts.append(f"{symbol} {int(value):,}")
        except (TypeError, ValueError):
            amounts.append(str(value))

    suffix = PERIOD_LABELS.get(str(period or "").strip().lower(), "")
    display = "{} {}".format(" - ".join(amounts), suffix).strip() if amounts else ""

    return {
        "salary": display,
        "salary_min": to_number(low),
        "salary_max": to_number(high),
        "currency": code,
        "salary_period": str(period or "").strip().lower(),
    }


def parse_iso(value):
    """Normalisasi timestamp ISO/UTC menjadi string ISO 8601."""
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return ""
    return parsed.isoformat(timespec="seconds")


def parse_posted_text(value, now=None):
    """Perkirakan ``posted_at`` dari teks relatif seperti '3d ago'.

    Tidak semua situs memberikan tanggal absolut; bila pola tidak dikenali,
    fungsi mengembalikan '' dan kolom ``posted_date`` tetap dipakai.
    """
    text = str(value or "").strip().lower()
    if not text:
        return ""

    now = now or datetime.now(timezone.utc)
    if text.startswith(("just now", "baru saja", "today", "hari ini")):
        return now.isoformat(timespec="seconds")
    if text.startswith(("yesterday", "kemarin")):
        return (now - timedelta(days=1)).isoformat(timespec="seconds")

    match = re.search(
        r"(\d+)\s*(second|minute|hour|day|week|month|year|"
        r"detik|menit|jam|hari|minggu|bulan|tahun|mo|d|h|w|y)s?\b",
        text,
    )
    if not match:
        return ""
    seconds = int(match.group(1)) * _UNIT_SECONDS[match.group(2)]
    return (now - timedelta(seconds=seconds)).isoformat(timespec="seconds")


def relative_date(created):
    """Format datetime sebagai 'Posted 3d ago' (naive = waktu lokal)."""
    if created is None:
        return ""
    now = datetime.now(timezone.utc) if created.tzinfo else datetime.now()
    delta = now - created
    days = delta.days
    if days < 0:
        return "Today"
    if days == 0:
        hours = int(delta.seconds // 3600)
        return "Just now" if hours < 1 else f"Posted {hours}h ago"
    if days < 7:
        return f"Posted {days}d ago"
    if days < 30:
        return f"Posted {days // 7}w ago"
    if days < 365:
        return f"Posted {days // 30}mo ago"
    return f"Posted {days // 365}y ago"


def job_fingerprint(job):
    """Kunci dedup lintas sumber: judul + perusahaan + kota (normal)."""
    def norm(value):
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

    return (
        norm(job.get("title")),
        norm(job.get("company")),
        norm(job.get("location")),
    )
