# KARTIKA Intel — Digital Information Threat Intelligence Platform

MVP platform intelijen ancaman informasi digital untuk tema **Kartika Cyber Hackathon 2026**.
Membantu analis memeriksa konten yang berpotensi menyesatkan, provokatif, terkoordinasi, atau
menunjukkan sinyal otomatisasi — dengan skor yang selalu bersifat **indikatif** dan disertai bukti
serta batasan.

Backend memakai **Django + Django REST Framework**, frontend memakai **React + TypeScript + Vite**.

## Fitur yang sudah berjalan

- **Ingest** URL artikel (Trafilatura + BeautifulSoup) atau teks manual.
- **Ingest media sosial publik** — tautan TikTok, Instagram, Facebook, dan X/Twitter diambil
  lewat UnifAPI: caption/teks, akun, waktu unggah, dan URL kanonis. Video/audio tidak ditranskripsi.
- **Hoax & fact-checking signal** — atribusi sumber, sensasionalisme, tekanan menyebarkan,
  klaim numerik tanpa sumber, ekstraksi kandidat klaim.
- **Pemeriksaan fakta eksternal** — Google Fact Check Tools API dicari untuk judul dan klaim
  utama, hasilnya disaring relevansinya, di-cache 7 hari, dan ditampilkan sebagai panel bukti
  pendukung (verdict heuristik tidak diubah).
- **Verifikasi klaim berbasis AI (opsional)** — dua klaim utama dicari ke pencarian web terbuka
  (Exa), lalu model bahasa menilai tiap klaim **hanya** dari cuplikan yang ditemukan. Hasilnya
  status per klaim (`didukung` / `dibantah` / `tidak cukup bukti`) beserta sitasi; sitasi yang
  tidak berasal dari hasil pencarian otomatis dibuang. Nonaktif bila kunci API kosong.
- **Provocation analysis** — leksikon kekerasan, dehumanisasi, mobilisasi, polarisasi, pola
  ajakan eskalasi, normalisasi panjang dokumen.
- **Coordinated activity analysis** — Jaccard similarity shingle 4-kata dalam jendela ±72 jam,
  tautan dua arah, pembaruan skor konten lama saat konten baru cocok.
- **Bot & AI content signals** — frasa templat model bahasa, keseragaman kalimat, tagar/mention
  berlebih, duplikasi internal. Dibatasi karena metadata akun belum tersedia.
- **Dashboard** — KPI, tren 14 hari, distribusi status, profil radar sinyal, peringatan
  koordinasi, analisis terbaru.
- **Riwayat & detail analisis** — filter status, ringkasan, empat kartu sinyal, klaim, konten
  terkait, sumber/bukti, dan daftar batasan.
- **Django admin** untuk inspeksi data (konten, analisis, sinyal, klaim, bukti, tautan).

## Stack

| Lapisan | Teknologi |
| --- | --- |
| Backend | Python 3.12+ (diuji 3.13), Django 5.2 LTS, Django REST Framework 3.16 |
| Ekstraksi | httpx, BeautifulSoup4, Trafilatura |
| Media sosial | UnifAPI (TikTok, Instagram, Facebook, X/Twitter) |
| Database | SQLite untuk MVP; siap dipindah ke PostgreSQL |
| Admin/auth | Django admin, session auth (endpoint analisis terbuka untuk demo) |
| Frontend | React 18, TypeScript, Vite 6, Tailwind CSS, Lucide, Recharts, React Router, TanStack Query |
| Form & validasi | React Hook Form + Zod |
| Pengujian | Django TestCase + DRF APITestCase (68 tes) |

## Struktur proyek

```
.
├── backend/
│   ├── manage.py                  # entry point Django
│   ├── satria/                    # settings, urlconf, wsgi/asgi, logging
│   ├── intel/
│   │   ├── models.py              # content_items, analyses, signals, claims, evidence, links
│   │   ├── serializers.py         # kontrak JSON untuk React
│   │   ├── views.py               # API, health, penyajian SPA
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── analysis/              # mesin heuristik framework-agnostic
│   │   ├── services/              # analisis, ekstraksi, dashboard, build frontend
│   │   ├── management/commands/   # runserver, build_frontend
│   │   ├── migrations/
│   │   └── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── components/            # Layout, tabel analisis, UI reusable
│       ├── lib/                   # API client, tipe, label, util
│       └── pages/                 # Dashboard, Analisis Baru, Riwayat, Detail, Metodologi
└── legacy_fastapi_backend.zip     # arsip backend FastAPI sebelum migrasi (opsional)
```

## Menjalankan

### Setup pertama kali

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows (Git Bash)
# source .venv/bin/activate && pip install -r requirements.txt   # Linux/macOS
cp .env.example .env
```

Frontend tidak perlu disiapkan manual: `runserver` akan menjalankan `npm install` dan
`npm run build` bila `frontend/dist` belum ada (Node.js + npm diperlukan).

### Satu perintah

```bash
cd backend
.venv/Scripts/python manage.py runserver
```

Perintah ini otomatis:

1. menjalankan migrasi database,
2. membangun frontend React bila `frontend/dist` belum tersedia,
3. menjalankan server di <http://127.0.0.1:8000>.

Database dimulai kosong: aplikasi tidak lagi menyuntikkan data contoh, sehingga seluruh isi
riwayat berasal dari konten yang Anda analisis sendiri.

Alamat penting:

- Aplikasi: <http://127.0.0.1:8000>
- Django admin: <http://127.0.0.1:8000/admin/>
- Health check: <http://127.0.0.1:8000/health>
- API (browsable saat `DEBUG=true`): <http://127.0.0.1:8000/api/v1/analyses>

Buat akun admin:

```bash
cd backend
.venv/Scripts/python manage.py createsuperuser
```

### Mode pengembangan dengan hot reload UI

Jalankan dua terminal:

**Terminal 1 — Django**
```bash
cd backend
.venv/Scripts/python manage.py runserver
```

**Terminal 2 — Vite**
```bash
cd frontend
npm run dev
```

Buka <http://127.0.0.1:5173>. Vite mem-proxy `/api` ke Django di port 8000; origin ini sudah
diizinkan lewat `CORS_ORIGINS`. Untuk perubahan UI tanpa Vite, jalankan `manage.py build_frontend`
lalu refresh <http://127.0.0.1:8000>.

### Command penting

```bash
python manage.py migrate              # terapkan migrasi
python manage.py build_frontend       # build React ke frontend/dist
python manage.py createsuperuser      # akun admin
python manage.py test                 # 68 tes
```

## Konfigurasi backend

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `SECRET_KEY` | `dev-only-change-me` | Wajib diganti di produksi |
| `DEBUG` | `true` | Matikan di produksi |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Dipisah koma |
| `DATABASE_URL` | `sqlite:///./kartika_intel.db` | `postgresql://user:pass@host:5432/db` untuk PostgreSQL |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Origin Vite saat mode dev |
| `FETCH_TIMEOUT_SECONDS` | `15` | Timeout pengambilan artikel |
| `MAX_CONTENT_CHARS` | `60000` | Batas teks yang disimpan/dianalisis |
| `COORDINATION_SIMILARITY_THRESHOLD` | `0.28` | Ambang Jaccard pasangan narasi |
| `COORDINATION_WINDOW_HOURS` | `72` | Jendela waktu perbandingan |
| `COORDINATION_MIN_CORPUS` | `3` | Minimum korpus agar keyakinan koordinasi penuh |
| `FACTCHECK_ENABLED` | `true` | Nonaktif otomatis bila API key kosong atau saat `manage.py test` |
| `GOOGLE_FACTCHECK_API_KEY` | — | API key Google Fact Check Tools (aktifkan API-nya di Google Cloud Console) |
| `FACTCHECK_TIMEOUT_SECONDS` | `6` | Timeout panggilan pemeriksaan fakta |
| `FACTCHECK_MAX_QUERIES` | `2` | Jumlah kueri (judul + klaim) per analisis |
| `FACTCHECK_PAGE_SIZE` | `5` | Kandidat klaim yang diminta dari Google |
| `FACTCHECK_CACHE_TTL_HOURS` | `168` | Umur cache respons di tabel `factcheck_queries` |
| `FACTCHECK_MIN_OVERLAP` | `0.45` | Ambang porsi kata klaim yang harus muncul di konten |
| `FACTCHECK_LANGUAGE_CODE` | kosong | Batasi bahasa ulasan (`id`); kosong = semua bahasa |
| `AI_CLAIM_CHECK_ENABLED` | `true` | Verifikasi klaim berbasis AI; nonaktif otomatis saat `manage.py test` |
| `EXA_API_KEY` | — | Kunci pencarian web Exa; verifikasi klaim nonaktif bila kosong |
| `EXA_RESULTS_PER_CLAIM` | `3` | Jumlah sumber yang diambil per klaim |
| `CLAIM_CHECK_MAX_CLAIMS` | `2` | Klaim yang diverifikasi per analisis (hemat kuota) |
| `LLM_ENABLED` | `false` | Wajib `true` agar verifikasi klaim berjalan |
| `LLM_API_KEY`, `LLM_MODEL` | — | Kunci dan nama model bahasa |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Endpoint kompatibel OpenAI (Groq, Gemini, OpenRouter, Ollama) |
| `UNIFAPI_API_KEY` | — | Kunci UnifAPI untuk ingest TikTok/Instagram/Facebook/X; tanpa kunci, URL media sosial ditolak dengan pesan agar teks ditempel manual |
| `UNIFAPI_BASE_URL` | `https://api.unifapi.com` | Endpoint UnifAPI |
| `SOCIAL_FETCH_TIMEOUT_SECONDS` | `15` | Timeout pengambilan satu postingan media sosial |

### Pindah ke PostgreSQL

1. Pasang driver: `pip install "psycopg[binary]"` (belum masuk requirements default).
2. Buat database lewat pgAdmin atau `createdb kartika_intel`.
3. Set `DATABASE_URL=postgresql://satria:satria@localhost:5432/kartika_intel` di `.env`.
4. Jalankan `python manage.py migrate`.

Django tetap memakai `manage.py`; tidak ada Alembic/SQLAlchemy pada versi ini.

## API

| Metode | Path | Keterangan |
| --- | --- | --- |
| `POST` | `/api/v1/analyses` | Analisis `{ "url": ... }` (artikel atau postingan TikTok/Instagram/Facebook/X) atau `{ "text": ..., "title"?, "publisher"? }` |
| `GET` | `/api/v1/analyses` | Riwayat; filter `verdict`, `category`; `limit` (1–100), `offset` |
| `GET` | `/api/v1/analyses/{id}` | Detail sinyal, klaim, bukti, konten terkait |
| `DELETE` | `/api/v1/analyses/{id}` | Hapus satu analisis beserta sinyal, klaim, bukti, dan tautan koordinasinya |
| `POST` | `/api/v1/analyses/bulk-delete` | Hapus beberapa analisis sekaligus `{ "ids": [...] }` (maks 200) |
| `GET` | `/api/v1/dashboard/summary` | Agregasi dashboard 14 hari |
| `GET` | `/health` | Status layanan |

Status error: `400` validasi input, `422` URL tidak aman atau isi hasil ekstraksi terlalu pendek,
`404` data tidak ditemukan, `502` sumber gagal diambil. Semua error memakai bentuk
`{"detail": "..."}` agar mudah ditampilkan frontend.

Penghapusan bersifat permanen. `ContentItem` ikut dihapus hanya bila tidak lagi dipakai analisis
lain, sehingga URL yang pernah dianalisis berulang tetap menyimpan kontennya.

Contoh:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyses \
  -H "Content-Type: application/json" \
  -d '{"text": "Pemerintah akan memadamkan listrik nasional selama 3 hari. Kabarnya keputusan ini diambil diam-diam. Sebarkan sebelum dihapus!", "title": "Uji"}'
```

## Model penilaian

Empat sinyal diskalakan 0–100 dengan bobot:

| Dimensi | Bobot |
| --- | --- |
| Hoax & fakta | 35% |
| Provokasi | 30% |
| Koordinasi | 20% |
| Bot & AI | 15% |

Skor risiko = **65% sinyal terkuat + 35% rata-rata berbobot**. Tingkat risiko: rendah 0–24,
sedang 25–49, tinggi 50–74, kritis 75–100.

Status analisis dipilih berurutan: indikasi terkoordinasi (≥2 konten mirip dan skor koordinasi
≥60) → terindikasi hoax (hoax ≥60) → provokatif (provokasi ≥60) → perlu verifikasi →
terindikasi fakta.

- Jika `GOOGLE_FACTCHECK_API_KEY` diisi, judul artikel dan maksimal dua klaim hasil ekstraksi
  dikirim ke Google Fact Check Tools API. Hasil dengan tumpang tindih kata rendah dibuang.
  Temuan disimpan di `Analysis.factcheck` dan sebagai `Evidence` berjenis `factcheck`.
- Sesuai prinsip retrieval, hasil pemeriksaan fakta **tidak mengubah verdict**. Ia hanya
  memberi konteks, digabung ke daftar batasan, dan dapat diaudit analis.
- Kegagalan API (kuota, jaringan, key salah) tidak menggagalkan analisis: status menjadi
  `unavailable` dan catatan batasan diganti sesuai kondisi.

Detail metode dan batasan tersedia di halaman **Metodologi** pada aplikasi.

## Batasan penting

- Pemeriksaan fakta eksternal hanya mencakup klaim yang sudah diperiksa pihak lain; konten baru
  tidak akan punya catatan, dan ketiadaan catatan bukan bukti kebenaran.
- Status klaim berbasis AI adalah pembacaan model terhadap cuplikan sumber, bukan putusan fakta.
  Tanpa sitasi yang valid statusnya diturunkan menjadi “tidak cukup bukti”, dan setiap sitasi
  tetap wajib dibuka analis.
- Ingest media sosial hanya membaca postingan **publik** dan hanya caption/teksnya; video dan audio
  tidak ditranskripsi, dan kegagalan penyedia mengembalikan `422`/`502` tanpa analisis parsial.
- Ingest media sosial menambah biaya per record di UnifAPI dan tidak menelusuri akun lain yang
  menyebarkan konten yang sama; tautan pendek di luar domain platform harus dibuka dulu.
- Sinyal bot/AI hanya berbasis teks karena metadata akun belum tersedia.
- Leksikon dapat melewatkan sarkasme, kutipan berita, atau konteks budaya.
- Kemiripan teks bukan bukti aktor yang sama (bisa karena sindikasi berita).
- Endpoint analisis sengaja terbuka untuk demo; gunakan autentikasi/token sebelum produksi.
- Keputusan akhir selalu berada pada analis manusia.

## Reset database

Hentikan server, hapus `backend/kartika_intel.db`, lalu jalankan `manage.py runserver` lagi.
Migrasi berjalan otomatis dan database dimulai kosong tanpa data contoh.

## Langkah berikutnya

1. Pakai LLM juga untuk ringkasan naratif dan penalaran verdict (saat ini AI hanya memberi status
   per klaim; verdict tetap heuristik).
2. Proteksi API dengan token/session auth dan peran analis/supervisor.
3. Impor batch CSV/JSON untuk metadata akun dan waktu unggah.
4. Integrasi MAFINDO/Yudistira API sebagai sumber pemeriksaan fakta lokal, di samping Google.
5. Ekspor laporan investigasi (PDF/DOCX) dan notifikasi klaster baru.
6. Deployment produksi: `DEBUG=false`, `collectstatic`, WhiteNoise/Gunicorn, PostgreSQL.
