"""Render scraping results into a single self-contained HTML file.

The generated page needs no web server: CSS and JavaScript are inline, and the
job data is embedded as JSON inside the page.
"""

import html
import json
import math
from string import Template

import pandas as pd

COLUMNS = [
    "source",
    "keyword",
    "job_id",
    "title",
    "url",
    "company",
    "location",
    "salary",
    "work_type",
    "posted_date",
    "description",
    "skills",
    "scraped_at",
]

TEMPLATE = Template(
    """<!doctype html>
<html lang="id" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$TITLE</title>
<style>
:root {
  --primary: #6366F1;
  --primary-soft: #EEF2FF;
  --bg: #F6F7FB;
  --card: #FFFFFF;
  --border: #E5E7EB;
  --text: #0F172A;
  --muted: #64748B;
}
html[data-theme="dark"] {
  --primary: #818CF8;
  --primary-soft: #1E1B4B;
  --bg: #0B1120;
  --card: #111A2E;
  --border: #1E293B;
  --text: #E2E8F0;
  --muted: #94A3B8;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  line-height: 1.5;
}
a { color: var(--primary); }
.wrap { max-width: 1200px; margin: 0 auto; padding: 24px; }
.hero {
  position: relative;
  background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 55%, #A855F7 100%);
  border-radius: 18px;
  padding: 28px 30px;
  color: #fff;
  box-shadow: 0 10px 30px rgba(99, 102, 241, .35);
}
.hero-badge {
  display: inline-block;
  background: rgba(255, 255, 255, .18);
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.hero h1 { font-size: 27px; margin: 12px 0 6px; letter-spacing: -.3px; }
.hero p { margin: 0; opacity: .92; font-size: 14px; }
.hero button {
  position: absolute;
  right: 24px;
  top: 24px;
  color: #fff;
  border-color: rgba(255, 255, 255, .45);
  background: rgba(255, 255, 255, .12);
}
button, select, input {
  font: inherit;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  padding: 9px 12px;
}
button { cursor: pointer; font-weight: 600; }
button:hover:not(:disabled) { border-color: var(--primary); }
button:disabled { opacity: .5; cursor: not-allowed; }
button.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}
.kpi-row { display: flex; gap: 16px; flex-wrap: wrap; margin: 18px 0 10px; }
.kpi {
  flex: 1 1 170px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px 20px;
}
.kpi .icon { font-size: 22px; }
.kpi .num { font-size: 30px; font-weight: 800; color: var(--primary); }
.kpi .lbl {
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  font-weight: 700;
  letter-spacing: .5px;
}
.panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 18px;
}
.panel h2 { font-size: 19px; margin: 0 0 8px; }
.meta-grid { display: flex; gap: 12px 28px; flex-wrap: wrap; font-size: 14px; }
.meta-grid b { color: var(--muted); font-weight: 600; }
.hint { color: var(--muted); font-size: 13px; margin: 12px 0 0; }
.note { color: #B45309; font-size: 13px; margin-top: 8px; font-weight: 600; }
.toolbar { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
.toolbar input { flex: 1 1 260px; }
.downloads { display: flex; gap: 10px; flex-wrap: wrap; }
.downloads a {
  text-decoration: none;
  padding: 9px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--primary);
  font-weight: 600;
}
.downloads a:hover { border-color: var(--primary); }
.count { color: var(--muted); font-size: 13.5px; margin: 4px 0 14px; }
.job {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 14px;
}
.job:hover { box-shadow: 0 8px 22px rgba(16, 24, 40, .10); }
.job-top { display: flex; align-items: baseline; gap: 10px; }
.job-no {
  flex: none;
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 2px 9px;
  border-radius: 6px;
}
.job-title { font-size: 17px; font-weight: 700; text-decoration: none; color: var(--text); }
a.job-title:hover { color: var(--primary); }
.job-company { color: var(--primary); font-weight: 600; font-size: 14px; margin-top: 6px; }
.job-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 11px; }
.chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 11px;
  border-radius: 999px;
  font-size: 12.5px;
  background: var(--primary-soft);
  border: 1px solid var(--border);
}
.chip.location { color: var(--primary); }
.chip.salary { background: rgba(16, 185, 129, .10); color: #059669; }
.chip.type { background: rgba(245, 158, 11, .10); color: #B45309; }
.chip.date { background: rgba(148, 163, 184, .12); color: var(--muted); }
.chip.source-jobstreet { color: #6366F1; font-weight: 700; }
.chip.source-glints { color: #DB2777; font-weight: 700; }
.chip.source-linkedin { color: #0A66C2; font-weight: 700; }
.chip.source-techinasia { color: #059669; font-weight: 700; }
details.job-desc { margin-top: 12px; border-top: 1px dashed var(--border); padding-top: 10px; }
details.job-desc summary { cursor: pointer; font-size: 13px; font-weight: 700; color: var(--primary); }
details.job-desc .body {
  margin-top: 10px;
  font-size: 13.5px;
  white-space: pre-wrap;
  max-height: 280px;
  overflow: auto;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
}
.table-wrap { overflow: auto; border: 1px solid var(--border); border-radius: 12px; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { background: var(--primary-soft); font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }
tr:last-child td { border-bottom: none; }
.pager { display: flex; gap: 14px; align-items: center; justify-content: center; margin: 20px 0; }
.page-info { color: var(--muted); font-size: 13.5px; }
.empty { color: var(--muted); padding: 30px; text-align: center; }
footer { color: var(--muted); font-size: 12px; text-align: center; padding: 20px 0 8px; }
@media (max-width: 640px) {
  .wrap { padding: 14px; }
  .hero button { position: static; margin-top: 16px; }
}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <span class="hero-badge">Glints · LinkedIn · Tech in Asia</span>
    <h1>Job Scraper</h1>
    <p>Hasil scraping lowongan kerja — dibuka langsung di browser tanpa server.</p>
    <button id="theme-toggle" type="button">🌙 Gelap</button>
  </div>

  <div class="kpi-row">$KPI</div>

  <div class="panel">
    <h2>Informasi</h2>
    <div class="meta-grid">$META</div>
    <p class="hint">Filter di halaman ini hanya mengubah tampilan. Jalankan <code>python main.py</code> lagi untuk mendapatkan data terbaru.</p>
  </div>

  <div class="panel">
    <h2>Simpan / Unduh</h2>
    <div class="downloads">$DOWNLOADS</div>
    <p class="hint">File hasil scraping tersimpan satu folder dengan halaman ini.</p>
  </div>

  <div class="panel">
    <h2>Hasil Pencarian</h2>
    <div class="toolbar">
      <input id="filter-text" type="search" placeholder="Cari judul, perusahaan, lokasi, skill...">
      <select id="filter-source" aria-label="Filter sumber">$SOURCE_OPTIONS</select>
      <select id="per-page" aria-label="Jumlah per halaman">
        <option value="20">20 per halaman</option>
        <option value="50">50 per halaman</option>
        <option value="100">100 per halaman</option>
        <option value="all">Semua</option>
      </select>
      <button id="view-toggle" type="button">📋 Lihat tabel</button>
    </div>
    <div class="count" id="count"></div>
    <div id="results"></div>
    <div class="pager" id="pager"></div>
  </div>

  <footer>Dibuat $GENERATED · $SOURCE_COUNT lowongan dari $SOURCE_LABEL</footer>
</div>

<script id="job-data" type="application/json">$DATA_JSON</script>
<script>
(function () {
  var jobs = JSON.parse(document.getElementById('job-data').textContent);
  var state = { page: 1, perPage: 20, view: 'cards' };

  function byId(id) { return document.getElementById(id); }

  function chip(value, cls) {
    if (value === null || value === undefined || String(value).trim() === '') return null;
    var span = document.createElement('span');
    span.className = 'chip ' + (cls || '');
    span.textContent = String(value);
    return span;
  }

  function addChip(parent, value, cls) {
    var el = chip(value, cls);
    if (el) parent.appendChild(el);
  }

  // Only http(s) links become clickable; blocks javascript: from scraped data.
  function safeUrl(raw) {
    try {
      var parsed = new URL(String(raw || ''), window.location.href);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return parsed.href;
    } catch (err) {}
    return '';
  }

  function titleNode(job) {
    var label = job.title || '(tanpa judul)';
    var url = safeUrl(job.url);
    if (!url) {
      var span = document.createElement('span');
      span.className = 'job-title';
      span.textContent = label;
      return span;
    }
    var link = document.createElement('a');
    link.className = 'job-title';
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = label;
    return link;
  }

  function matches(job, query, source) {
    if (source && source !== 'Semua sumber' && String(job.source || '') !== source) return false;
    if (!query) return true;
    // Deliberately excludes url/keyword/scraped_at: they are not useful to search.
    var fields = ['title', 'company', 'location', 'description', 'skills', 'source', 'salary', 'work_type', 'posted_date'];
    for (var i = 0; i < fields.length; i++) {
      var value = job[fields[i]];
      if (Array.isArray(value)) value = value.join(' ');
      if (String(value === null || value === undefined ? '' : value).toLowerCase().indexOf(query) !== -1) return true;
    }
    return false;
  }

  function renderCards(list, startNo) {
    var fragment = document.createDocumentFragment();
    list.forEach(function (job, index) {
      var card = document.createElement('article');
      card.className = 'job';

      var top = document.createElement('div');
      top.className = 'job-top';
      var no = document.createElement('span');
      no.className = 'job-no';
      no.textContent = String(startNo + index);
      top.appendChild(no);
      top.appendChild(titleNode(job));

      var company = document.createElement('div');
      company.className = 'job-company';
      company.textContent = job.company || '';

      var meta = document.createElement('div');
      meta.className = 'job-meta';
      var src = String(job.source || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
      addChip(meta, job.source, 'source-' + src);
      addChip(meta, job.location, 'location');
      addChip(meta, job.salary, 'salary');
      addChip(meta, job.work_type, 'type');
      addChip(meta, job.posted_date, 'date');

      var details = document.createElement('details');
      details.className = 'job-desc';
      var summary = document.createElement('summary');
      summary.textContent = 'Lihat deskripsi';
      var body = document.createElement('div');
      body.className = 'body';
      body.textContent = job.description || '(tidak tersedia)';
      details.appendChild(summary);
      details.appendChild(body);

      card.appendChild(top);
      card.appendChild(company);
      card.appendChild(meta);
      card.appendChild(details);
      fragment.appendChild(card);
    });
    return fragment;
  }

  function renderTable(list, startNo) {
    var wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    var table = document.createElement('table');
    var head = document.createElement('thead');
    var headRow = document.createElement('tr');
    ['No', 'Judul', 'Perusahaan', 'Sumber', 'Lokasi', 'Gaji', 'Tipe', 'Tanggal'].forEach(function (label) {
      var th = document.createElement('th');
      th.textContent = label;
      headRow.appendChild(th);
    });
    head.appendChild(headRow);

    var body = document.createElement('tbody');
    list.forEach(function (job, index) {
      var row = document.createElement('tr');
      var values = [String(startNo + index), '', job.company || '', job.source || '', job.location || '', job.salary || '', job.work_type || '', job.posted_date || ''];
      values.forEach(function (value, column) {
        var cell = document.createElement('td');
        if (column === 1) cell.appendChild(titleNode(job));
        else cell.textContent = value;
        row.appendChild(cell);
      });
      body.appendChild(row);
    });
    table.appendChild(head);
    table.appendChild(body);
    wrap.appendChild(table);
    return wrap;
  }

  function renderPager(pages) {
    var holder = byId('pager');
    holder.textContent = '';
    if (pages <= 1) return;

    var prev = document.createElement('button');
    prev.type = 'button';
    prev.textContent = '← Sebelumnya';
    prev.disabled = state.page === 1;
    prev.onclick = function () { state.page -= 1; render(); };

    var info = document.createElement('span');
    info.className = 'page-info';
    info.textContent = 'Halaman ' + state.page + ' dari ' + pages;

    var next = document.createElement('button');
    next.type = 'button';
    next.textContent = 'Berikutnya →';
    next.disabled = state.page === pages;
    next.onclick = function () { state.page += 1; render(); };

    holder.appendChild(prev);
    holder.appendChild(info);
    holder.appendChild(next);
  }

  function render() {
    var query = byId('filter-text').value.trim().toLowerCase();
    var source = byId('filter-source').value;
    var rows = jobs.filter(function (job) { return matches(job, query, source); });

    var perValue = byId('per-page').value;
    var perPage = perValue === 'all' ? rows.length : parseInt(perValue, 10);
    if (!perPage || perPage < 1) perPage = rows.length || 1;
    var pages = Math.max(1, Math.ceil(rows.length / perPage));
    if (state.page > pages) state.page = pages;

    var start = (state.page - 1) * perPage;
    var shown = rows.slice(start, start + perPage);
    byId('count').textContent = 'Menampilkan ' + shown.length + ' dari ' + rows.length + ' lowongan' + (rows.length ? ' (halaman ' + state.page + '/' + pages + ')' : '');

    var host = byId('results');
    host.textContent = '';
    byId('pager').textContent = '';
    if (!shown.length) {
      var empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = 'Tidak ada lowongan yang cocok dengan filter.';
      host.appendChild(empty);
      return;
    }
    host.appendChild(state.view === 'table' ? renderTable(shown, start + 1) : renderCards(shown, start + 1));
    renderPager(pages);
  }

  byId('filter-text').addEventListener('input', function () { state.page = 1; render(); });
  byId('filter-source').addEventListener('change', function () { state.page = 1; render(); });
  byId('per-page').addEventListener('change', function () { state.page = 1; render(); });
  byId('view-toggle').addEventListener('click', function () {
    state.view = state.view === 'cards' ? 'table' : 'cards';
    byId('view-toggle').textContent = state.view === 'cards' ? '📋 Lihat tabel' : '🃏 Lihat kartu';
    render();
  });
  byId('theme-toggle').addEventListener('click', function () {
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.documentElement.setAttribute('data-theme', dark ? 'light' : 'dark');
    byId('theme-toggle').textContent = dark ? '🌙 Gelap' : '☀️ Terang';
  });

  render();
})();
</script>
</body>
</html>
"""
)


def _clean(value):
    """Make a value JSON-safe (pandas NA, numpy scalars, lists, dictionaries)."""
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float) and math.isnan(value):
        return ""
    try:
        if value is None or pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return value


def _kpi(df):
    cards = [
        ("💼", len(df), "Total Lowongan"),
        ("🏢", df["company"].nunique() if "company" in df else 0, "Perusahaan"),
        ("📍", df["location"].nunique() if "location" in df else 0, "Kota"),
        (
            "💰",
            int(df["salary"].fillna("").astype(str).str.strip().ne("").sum())
            if "salary" in df
            else 0,
            "Dengan Gaji",
        ),
    ]
    return "".join(
        '<div class="kpi"><div class="icon">{icon}</div>'
        '<div class="num">{value}</div><div class="lbl">{label}</div></div>'.format(
            icon=icon, value=value, label=html.escape(label)
        )
        for icon, value, label in cards
    )


def render_html(df, path, base_name, meta):
    """Write a self-contained HTML report to *path* and return the path."""
    records = [
        {column: _clean(row.get(column)) for column in COLUMNS}
        for row in df.to_dict(orient="records")
    ]
    data_json = json.dumps(records, ensure_ascii=False, default=str)
    # Keep embedded JSON inside the <script>; also escape JS line separators.
    data_json = data_json.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    # Derive options from actual records, not from the requested source list.
    sources = sorted(
        {str(row.get("source")) for row in records if str(row.get("source") or "").strip()}
    )
    source_options = '<option value="Semua sumber">Semua sumber</option>' + "".join(
        '<option value="{value}">{value}</option>'.format(value=html.escape(source))
        for source in sources
    )

    kpi_html = _kpi(df)
    # `notes` carries per-source warnings collected by main.run_scrape().
    notes = meta.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]
    notes_html = "".join(
        '<div class="note">⚠️ {text}</div>'.format(text=html.escape(str(note)))
        for note in notes
        if str(note).strip()
    )
    meta_html = (
        "<div><b>Kata kunci:</b> {keyword}</div>"
        "<div><b>Sumber:</b> {sources}</div>"
        "<div><b>Lokasi:</b> {location}</div>"
        "<div><b>Dibuat:</b> {generated}</div>{notes}"
    ).format(
        keyword=html.escape(str(meta.get("keyword", ""))),
        sources=html.escape(", ".join(meta.get("sources", [])) or "-"),
        location=html.escape(str(meta.get("location", "")) or "-"),
        generated=html.escape(str(meta.get("generated_at", ""))),
        notes=notes_html,
    )

    downloads = "".join(
        '<a href="{name}.{ext}" download="{name}.{ext}">↓ {label}</a>'.format(
            name=html.escape(base_name, quote=True),
            ext=ext,
            label=label,
        )
        for ext, label in (("csv", "CSV"), ("xlsx", "Excel"), ("json", "JSON"))
    )

    page = TEMPLATE.substitute(
        TITLE="Job Scraper - " + html.escape(str(meta.get("keyword", ""))),
        KPI=kpi_html,
        META=meta_html,
        DOWNLOADS=downloads,
        SOURCE_OPTIONS=source_options,
        DATA_JSON=data_json,
        GENERATED=html.escape(str(meta.get("generated_at", ""))),
        SOURCE_COUNT=str(len(df)),
        SOURCE_LABEL=html.escape(", ".join(sources) or "semua sumber"),
    )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    return path
