# Job Scraper

Aplikasi command-line untuk mengambil lowongan kerja dari beberapa situs, lalu menyimpannya sebagai **HTML, CSV, Excel, dan JSON**. Laporan HTML bersifat *self-contained*: bisa langsung dibuka di browser tanpa server atau koneksi internet.

> **Catatan nama:** repository ini bernama `job-auto-applier`, tetapi versi ini hanya melakukan **scraping + pelaporan**. Proses apply lamaran, tracking status, dan notifikasi belum tersedia.

---

## Daftar isi

- [Fitur](#fitur)
- [Instalasi](#instalasi)
- [Pemakaian cepat](#pemakaian-cepat)
- [Opsi command-line](#opsi-command-line)
- [Konfigurasi (`config.json`)](#konfigurasi-configjson)
- [Contoh penggunaan](#contoh-penggunaan)
- [Hasil output](#hasil-output)
- [Membaca laporan HTML](#membaca-laporan-html)
- [Environment variable](#environment-variable)
- [Troubleshooting](#troubleshooting)
- [Keterbatasan](#keterbatasan)
- [Menjalankan test](#menjalankan-test)
- [Struktur file](#struktur-file)
- [Catatan etis/legal](#catatan-etislegal)

---

## Fitur

- Multi-sumber: **Glints**, **LinkedIn**, dan **Tech in Asia**.
- Detail lowongan: judul, perusahaan, lokasi, gaji, tipe kerja, tanggal, deskripsi, dan skill.
- Output sekaligus: HTML interaktif + CSV + Excel + JSON.
- Filter teks, filter sumber, pagination, dan toggle kartu/tabel di laporan HTML.
- Peringatan bila suatu sumber gagal atau menghasilkan 0 lowongan.
- Konfigurasi lewat file JSON dan/atau flag command-line.

---

## Instalasi

Butuh **Python 3.9+**.

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Install dependency:

```bash
pip install -r requirements.txt
```

Untuk menjalankan test (opsional):

```bash
pip install -r requirements-dev.txt
```

---

## Pemakaian cepat

Jalankan dari folder repository:

```bash
python main.py
```

Ini memakai nilai dari `config.json` dan menulis hasil ke folder `output/`.

Contoh dengan flag:

```bash
python main.py --keyword "python" --sources Glints LinkedIn --pages 2 --max-jobs 10
```

> **Tips:** untuk sumber dengan spasi, pakai tanda kutip: `--sources "Tech in Asia"`.

---

## Opsi command-line

| Opsi | Default | Penjelasan |
| --- | --- | --- |
| `--keyword` | dari config | Kata kunci posisi/skill yang dicari. Wajib tidak kosong. |
| `--sources` | dari config | Satu atau beberapa sumber: `Glints`, `LinkedIn`, `Tech in Asia`. |
| `--location` | dari config | Lokasi pencarian. Dipakai Glints, LinkedIn, dan Tech in Asia. |
| `--pages`, `--max-pages` | dari config | Jumlah halaman per sumber (minimum 1). |
| `--delay` | dari config | Jeda antar request dalam detik (minimum 0). |
| `--max-jobs` | dari config | Batas lowongan per sumber. `0` berarti semua. |
| `--config` | `config.json` | Path ke file konfigurasi JSON lain. |

Flag yang diberikan selalu **meng-override** nilai di file config.

**Exit code:** `0` = sukses, `1` = config tidak valid atau tidak ada lowongan yang ditemukan.

---

## Konfigurasi (`config.json`)

```json
{
  "keyword": "data analyst",
  "sources": ["Glints", "LinkedIn", "Tech in Asia"],
  "location": "Indonesia",
  "max_pages": 3,
  "delay": 1.0,
  "max_jobs": 0
}
```

| Key | Tipe | Default | Arti |
| --- | --- | --- | --- |
| `keyword` | string | `data analyst` | Kata kunci pencarian. |
| `sources` | array/string | 3 sumber di atas | Sumber yang dipakai. Jobstreet tidak didukung. |
| `location` | string | `Indonesia` | Filter lokasi. |
| `max_pages` | number | `3` | Jumlah halaman. |
| `delay` | number | `1.0` | Jeda antar request (detik). |
| `max_jobs` | number | `0` | Batas per sumber; `0` = tanpa batas. |

Key lain di luar tabel diabaikan. Kalau file config tidak ada atau rusak, aplikasi memakai default dan menampilkan peringatan.

---

## Contoh penggunaan

**Cari 10 lowongan Python dari Glints saja:**

```bash
python main.py --keyword python --sources Glints --max-jobs 10
```

**Cari di LinkedIn + Tech in Asia, 2 halaman, jeda 2 detik:**

```bash
python main.py --keyword "data scientist" --sources LinkedIn "Tech in Asia" --pages 2 --delay 2
```

**Pakai file config lain:**

```bash
python main.py --config config-produksi.json
```

**Mode aman untuk testing cepat:**

```bash
python main.py --sources Glints --pages 1 --max-jobs 3 --delay 1
```

---

## Hasil output

File dibuat di folder `output/` dengan pola nama:

```text
output/<keyword>_<YYYYmmdd_HHMMSS>.html
output/<keyword>_<YYYYmmdd_HHMMSS>.csv
output/<keyword>_<YYYYmmdd_HHMMSS>.xlsx
output/<keyword>_<YYYYmmdd_HHMMSS>.json
```

Contoh:

```text
output/data-analyst_20261124_143644.html
```

Setiap run membuat file baru, jadi hasil lama tidak ditimpa. Folder `output/` sudah masuk `.gitignore`.

---

## Membaca laporan HTML

Buka file `.html` di browser. Tidak perlu server.

Yang bisa dilakukan:

- **Kotak pencarian** — cari judul, perusahaan, lokasi, deskripsi, skill, gaji, dan sumber.
- **Dropdown sumber** — filter ke satu sumber tertentu.
- **Jumlah per halaman** — 20 / 50 / 100 / semua.
- **Tombol kartu/tabel** — ganti tampilan hasil.
- **Tombol gelap/terang** — ganti tema.
- **Tombol navigasi** — halaman berikutnya/sebelumnya.
- **Tautan unduh** — CSV, Excel, JSON (file harus tetap satu folder dengan HTML).

Panel **Informasi** menampilkan kata kunci, sumber, lokasi, waktu generate, dan catatan peringatan bila ada sumber yang kosong.

> Filter di HTML hanya mengubah tampilan. Untuk mendapat data baru, jalankan `python main.py` lagi.

---

## Environment variable

Kredensial Algolia untuk Tech in Asia bisa di-override:

```powershell
# Windows PowerShell
$env:TECHINASIA_ALGOLIA_APP_ID = "APP_ID"
$env:TECHINASIA_ALGOLIA_API_KEY = "API_KEY"
python main.py --sources "Tech in Asia"
```

```bash
# macOS / Linux
export TECHINASIA_ALGOLIA_APP_ID="APP_ID"
export TECHINASIA_ALGOLIA_API_KEY="API_KEY"
python main.py --sources "Tech in Asia"
```

Tanpa env var, aplikasi memakai nilai default dan mencetak peringatan.

---

## Troubleshooting

| Gejala | Penjelasan / solusi |
| --- | --- |
| `Error: Jobstreet sedang tidak didukung (HTTP 403)` | Jobstreet sengaja dinonaktifkan. Pakai Glints, LinkedIn, atau Tech in Asia. |
| `⚠️ Glints: pagination belum didukung...` | Glints hanya mengambil 1 halaman. Turunkan `--pages 1` atau terima perilaku ini. |
| `⚠️ <sumber>: 0 lowongan...` | Bisa jadi memang tidak ada hasil, atau selector/API situs berubah. Coba kata kunci lain atau cek koneksi. |
| `⚠️ Tech in Asia: Algolia API key default...` | Informasi saja. Set env var di atas untuk menghilangkan peringatan. |
| `Tidak ada lowongan ditemukan.` | Semua sumber gagal atau kosong. Periksa keyword, lokasi, dan koneksi internet. |
| `ModuleNotFoundError: No module named ...` | Jalankan `pip install -r requirements.txt` di dalam virtual environment yang aktif. |
| `python: command not found` | Pakai `python3` di macOS/Linux, atau pastikan Python sudah masuk PATH di Windows. |

---

## Keterbatasan

- **Jobstreet dinonaktifkan** karena situs mengembalikan HTTP 403.
- **Glints hanya 1 halaman**; `max_pages` diterima agar config konsisten, tapi tidak menambah hasil.
- **Belum ada auto-apply**, tracking lamaran, atau notifikasi email.
- Gaji dan tanggal masih disimpan sebagai teks (mis. `"Rp 6,000,000 per month"`, `"Posted 3d ago"`), belum numeric/ISO.
- Dedup hanya per-sumber berdasarkan `job_id`, belum lintas sumber.
- Filter di laporan HTML tidak diekspor ke CSV/JSON.

---

## Menjalankan test

```bash
python -m pytest
```

Test mencakup: validasi CLI, penolakan Jobstreet, URL Glints, override Algolia, dan render HTML (termasuk `$` pada gaji serta escaping `</script>`).

---

## Struktur file

```text
job-auto-applier/
├── main.py                  # CLI, orchestrasi, penulisan output
├── config.json              # Default konfigurasi
├── scraper.py               # Helper umum + scraper Jobstreet (deprecated)
├── glints_scraper.py        # Scraper Glints
├── linkedin_scraper.py      # Scraper LinkedIn (guest endpoint)
├── techinasia_scraper.py    # Scraper Tech in Asia via Algolia
├── html_report.py           # Generator laporan HTML mandiri
├── requirements.txt         # Dependency runtime
├── requirements-dev.txt     # Dependency test
├── tests/                   # Test pytest
└── output/                  # Hasil scraping (gitignore)
```

---

## Catatan etis/legal

Scraping situs pihak ketiga dapat melanggar Terms of Service. Gunakan jeda (`--delay`) yang wajar, hormati `robots.txt`, dan periksa kebijakan masing-masing situs sebelum memakai aplikasi untuk produksi.
