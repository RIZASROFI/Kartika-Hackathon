# KARTIKA Intel — Digital Information Threat Intelligence Platform

MVP platform intelijen ancaman informasi digital untuk tema **Kartika Cyber Hackathon 2026**.
Membantu analis memeriksa konten yang berpotensi menyesatkan — dengan skor yang selalu
bersifat **indikatif** dan disertai bukti serta batasan.

Backend memakai **Django + Django REST Framework**, frontend memakai **React + TypeScript + Vite**.

## Fitur yang sudah berjalan

- **Ingest** URL artikel (Trafilatura + BeautifulSoup) atau teks manual. Untuk postingan media
  sosial, salin teks/caption lalu tempelkan sebagai teks manual; video/audio tidak ditranskripsi.
- **Hoax & fact-checking signal** — atribusi sumber, sensasionalisme, tekanan menyebarkan,
  klaim numerik tanpa sumber, ekstraksi kandidat klaim.
- **Sinyal model IndoBERT lokal (opsional)** — paket `backend/models/cynteltika_indobert_v1`
  (tersedia di repo lewat Git LFS) dinilai per jendela 512 token sebagai sinyal **pembanding**. Skornya tidak
  pernah dipakai sebagai bukti dan tidak mengubah verdict; panel detail menampilkan keduanya.
- **Pemeriksaan fakta eksternal** — Google Fact Check Tools API dan basis data **MAFINDO
  Yudistira** dicari untuk judul dan klaim utama, hasilnya disaring relevansinya, di-cache
  7 hari, dan menjadi bukti bagi Evidence-Based Decision Engine.
- **Verifikasi klaim berbasis AI (opsional)** — dua klaim utama dicari ke pencarian web terbuka
  (Exa), lalu model bahasa menilai tiap klaim **hanya** dari cuplikan yang ditemukan. Hasilnya
  status per klaim (`didukung` / `dibantah` / `tidak cukup bukti`) beserta sitasi; sitasi yang
  tidak berasal dari hasil pencarian otomatis dibuang. Nonaktif bila kunci API kosong.
- **Evidence-Based Decision Engine (EBDE)** — verdict akhir dihitung dari bukti eksternal:
  relevansi × kredibilitas penerbit × kebaruan, dihitung per domain independen (duplikat tidak
  dihitung), konflik antarbukti dideteksi, dan verdict ditahan bila bukti belum cukup.
  `risk_score` narasi disimpan terpisah dan tidak dapat menggeser verdict.
- **Dashboard** — KPI, tren 14 hari, distribusi status, profil sinyal, analisis terbaru.
- **Riwayat & detail analisis** — filter status, ringkasan, kartu sinyal, klaim,
  sumber/bukti, dan daftar batasan.
- **Django admin** untuk inspeksi data (konten, analisis, sinyal, klaim, bukti).

## Stack

| Lapisan | Teknologi |
| --- | --- |
| Backend | Python 3.12+ (diuji 3.13), Django 5.2 LTS, Django REST Framework 3.16 |
| Ekstraksi | httpx, BeautifulSoup4, Trafilatura |
| Sinyal model | IndoBERT `cynteltika_indobert_v1` via torch (CPU) + transformers, opsional |
| Media sosial | Teks/caption ditempel manual (tanpa pengambilan otomatis) |
| Database | SQLite untuk MVP; siap dipindah ke PostgreSQL |
| Admin/auth | Django admin, session auth (endpoint analisis terbuka untuk demo) |
| Frontend | React 18, TypeScript, Vite 6, Tailwind CSS, Lucide, Recharts, React Router, TanStack Query |
| Form & validasi | React Hook Form + Zod |
| Pengujian | Django TestCase + DRF APITestCase (111 tes) |

## Struktur proyek

```
.
├── backend/
│   ├── manage.py                  # entry point Django
│   ├── satria/                    # settings, urlconf, wsgi/asgi, logging
│   ├── intel/
│   │   ├── models.py              # content_items, analyses, signals, claims, evidence
│   │   ├── serializers.py         # kontrak JSON untuk React
│   │   ├── views.py               # API, health, penyajian SPA
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── analysis/              # heuristik, sinyal IndoBERT, EBDE (framework-agnostic)
│   │   ├── services/              # analisis, ekstraksi, dashboard, build frontend
│   │   ├── management/commands/   # runserver, build_frontend
│   │   ├── migrations/
│   │   └── tests/
│   ├── models/                    # bobot IndoBERT lokal via Git LFS (~475 MB)
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

Bobot IndoBERT (~475 MB) disimpan lewat **Git LFS**. Jalankan sekali setelah clone agar bobot
terunduh:

```bash
git lfs install
git lfs pull
```

Tanpa bobot tersebut aplikasi tetap berjalan; hanya sinyal IndoBERT yang nonaktif.

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
python manage.py test                 # 111 tes
```

## Konfigurasi backend

Salin `backend/.env.example` menjadi `backend/.env` lalu isi nilainya. **Kunci API tidak disertakan
di dalam repo** demi keamanan: fitur yang membutuhkannya otomatis nonaktif bila nilainya kosong,
sehingga aplikasi tetap bisa dijalankan dan dinilai tanpa kunci apa pun.

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `SECRET_KEY` | `dev-only-change-me` | Wajib diganti di produksi |
| `DEBUG` | `true` | Matikan di produksi |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Dipisah koma |
| `DATABASE_URL` | `sqlite:///./kartika_intel.db` | `postgresql://user:pass@host:5432/db` untuk PostgreSQL |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Origin Vite saat mode dev |
| `FETCH_TIMEOUT_SECONDS` | `15` | Timeout pengambilan artikel |
| `MAX_CONTENT_CHARS` | `60000` | Batas teks yang disimpan/dianalisis |
| `INDOBERT_ENABLED` | `true` | Sinyal model lokal; nonaktif otomatis bila artefak model tidak ada atau saat `manage.py test` |
| `INDOBERT_MODEL_DIR` | `backend/models/cynteltika_indobert_v1` | Lokasi paket model (Git LFS) |
| `INDOBERT_MAX_TOKENS` | `512` | Panjang jendela token per potongan teks |
| `INDOBERT_MAX_CHUNKS` | `4` | Jumlah jendela yang dinilai per analisis (pembatas waktu) |
| `INDOBERT_BATCH_SIZE` | `4` | Jendela per batch inference |
| `FACTCHECK_ENABLED` | `true` | Nonaktif otomatis bila API key kosong atau saat `manage.py test` |
| `GOOGLE_FACTCHECK_API_KEY` | — | API key Google Fact Check Tools (aktifkan API-nya di Google Cloud Console) |
| `FACTCHECK_TIMEOUT_SECONDS` | `6` | Timeout panggilan pemeriksaan fakta |
| `FACTCHECK_MAX_QUERIES` | `2` | Jumlah kueri (judul + klaim) per analisis |
| `FACTCHECK_PAGE_SIZE` | `5` | Kandidat klaim yang diminta dari Google |
| `FACTCHECK_CACHE_TTL_HOURS` | `168` | Umur cache respons di tabel `factcheck_queries` |
| `FACTCHECK_MIN_OVERLAP` | `0.45` | Ambang porsi kata klaim yang harus muncul di konten |
| `FACTCHECK_LANGUAGE_CODE` | kosong | Batasi bahasa ulasan (`id`); kosong = semua bahasa |
| `MAFINDO_ENABLED` | `true` | Cek fakta MAFINDO/Yudistira; nonaktif otomatis bila key kosong atau saat `manage.py test` |
| `MAFINDO_API_KEY` | — | API key MAFINDO Public API v2 (diminta ke tim MAFINDO) |
| `MAFINDO_BASE_URL` | `https://yudistira.turnbackhoax.id/api` | Base URL Yudistira; tanpa trailing slash (server membalas 403) |
| `MAFINDO_TIMEOUT_SECONDS` | `8` | Timeout panggilan MAFINDO |
| `MAFINDO_PAGE_SIZE` | `5` | Kandidat artikel cek fakta per kueri |
| `MAFINDO_MAX_QUERIES` | `2` | Jumlah kata kunci MAFINDO per analisis (hemat kuota) |
| `AI_CLAIM_CHECK_ENABLED` | `true` | Verifikasi klaim berbasis AI; nonaktif otomatis saat `manage.py test` |
| `EXA_API_KEY` | — | Kunci pencarian web Exa; verifikasi klaim nonaktif bila kosong |
| `EXA_RESULTS_PER_CLAIM` | `3` | Jumlah sumber yang diambil per klaim |
| `CLAIM_CHECK_MAX_CLAIMS` | `2` | Klaim yang diverifikasi per analisis (hemat kuota) |
| `LLM_ENABLED` | `false` | Wajib `true` agar verifikasi klaim berjalan |
| `CLAIM_MATCH_ENABLED` | `true` | Pencocokan klaim temuan cek fakta dengan konten; nonaktif otomatis saat `manage.py test` |
| `LLM_API_KEY`, `LLM_MODEL` | — | Kunci dan nama model bahasa |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Endpoint kompatibel OpenAI (Groq, Gemini, OpenRouter, Ollama) |

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
| `GET` | `/api/v1/analyses/{id}` | Detail sinyal, klaim, bukti, dan jejak keputusan EBDE (`decision`) |
| `DELETE` | `/api/v1/analyses/{id}` | Hapus satu analisis beserta sinyal, klaim, dan buktinya |
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

Analisis menyimpan **dua keluaran yang tidak saling menggantikan**:

| Keluaran | Sumber | Arti |
| --- | --- | --- |
| `risk_score` 0–100 | sinyal heuristik (IndoBERT hanya pembanding) | pola penyebaran: atribusi lemah, sensasionalisme, tekanan menyebarkan |
| `verdict` | Evidence-Based Decision Engine (EBDE) | status klaim berdasarkan bukti eksternal |

Tingkat risiko: rendah 0–24, sedang 25–49, tinggi 50–74, kritis 75–100.

Sinyal narasi tidak pernah menjadi bukti. Verdict hanya ditetapkan EBDE dari temuan cek fakta dan
sitasi pencarian, dengan tiap bukti diberi bobot:

- **relevansi** — kecocokan kata penting dua arah (porsi bukti yang muncul pada klaim/konten,
  atau porsi klaim yang dicakup bukti; dipakai yang tertinggi agar artikel panjang yang
  benar-benar membahas klaim pendek tidak dihukum);
- **kredibilitas** — lembaga cek fakta 0,95; media mapan 0,85; domain pemerintah/kepolisian/
  akademik 0,80; media populer 0,70; platform UGC (blogspot/wordpress/medium/media sosial)
  0,30; domain lain 0,50;
- **kebaruan** — peluruhan eksponensial paruh 365 hari, 0,60 bila tanggal tidak diketahui;
- **independensi** — dihitung per domain memakai artikel terkuat, URL duplikat dibuang.

Bobot bukti = relevansi × kredibilitas × kebaruan. Status klaim dari model bahasa tidak dihitung
sebagai bukti tambahan: tiap URL sitasi menjadi satu item bukti, dan satu artikel cek fakta boleh
berdiri sendiri hanya bila kredibilitasnya ≥0,90 dan relevansinya ≥0,60.

Sebelum menimbang, tiap temuan cek fakta dicocokkan ke konten oleh model bahasa: **sama**,
**berbeda**, atau **tidak jelas**. Temuan untuk pernyataan lain (mis. pemeriksa fakta membantah
klaim “PN Surakarta menyatakan ijazah Jokowi palsu”, sedangkan konten melaporkan “Jokowi bersaksi
di PN Jakarta Timur”) disimpan sebagai **konteks** dan tidak menambah bobot maupun domain. Model
tidak menilai benar/salah; bila `CLAIM_MATCH_ENABLED=false` atau model gagal, pencocokan kata
lama dipakai dan statusnya tercatat di `decision.provider_status.claim_match`.

Verdict: **Terindikasi Fakta** / **Terindikasi Hoaks** bila sisi dominan ≥0,60 dan ≥70% bobot;
bila tidak ada sisi pembanding, ≥2 domain independen dengan bobot ≥0,40 sudah memutuskan;
**Campuran** bila kedua sisi ≥0,30 dan sisi lemah ≥50% sisi kuat; **Perlu Verifikasi** bila bukti
tipis atau tidak konvergen; **Belum Dapat Dinilai** bila tidak ada bukti. Alasan penahanan
disimpan di `decision.insufficient_reason`.

Bobot sinyal risiko (bukan bukti): tanpa atribusi yang dapat ditelusuri (+20), sumber kabur seperti “kabarnya”
atau “orang dalam” (+9 per frasa, maks 27), bahasa sensasional (maks 18), tekanan menyebarkan
(maks 24), pernyataan absolut (maks 10), angka tanpa atribusi (+12), tanpa rujukan lembaga
resmi (+10), serta otoritas semu — nama lembaga tanpa pernyataan resmi (+10). Atribusi yang
dapat ditelusuri (dilansir/pernyataan/juru bicara) dan rujukan lembaga menurunkan skor, dan
kata seperti “menurut” tanpa pihak konkret tidak dihitung sebagai atribusi.

- Jika `GOOGLE_FACTCHECK_API_KEY` diisi, judul artikel dan maksimal dua klaim hasil ekstraksi
  dikirim ke Google Fact Check Tools API. Hasil dengan tumpang tindih kata rendah dibuang.
  Temuan disimpan di `Analysis.factcheck` dan sebagai `Evidence` berjenis `factcheck`.
- Jika `MAFINDO_API_KEY` diisi, konten juga dicari ke MAFINDO Yudistira
  (`POST /antihoax/search`, key di body form). Pencarian MAFINDO mencocokkan **frasa utuh**
  (`ekspor gas` cocok, `gas singapura` tidak), jadi tiap kueri berupa satu kata kunci: nama diri
  didahulukan, sisanya kata terpanjang tanpa kata fungsi (maks `MAFINDO_MAX_QUERIES`).
  Judul artikel cek fakta dipakai sebagai klaim, dan tautan artikelnya diambil dari
  `claim_review` (dengan `references` sebagai cadangan).
- Kedua provider dijalankan terpisah: kegagalan satu provider (kuota, key salah, jaringan)
  tidak menghapus temuan provider lain, dan status gabungan tetap `matched` bila ada temuan.
- Hasil pemeriksaan fakta dan sitasi model menjadi **bukti** bagi EBDE, bukan verdict langsung:
  satu artikel tidak cukup untuk memutuskan, dan tiap item dapat diaudit analis.
- Kegagalan API (kuota, jaringan, key salah) tidak menggagalkan analisis: status menjadi
  `unavailable` dan catatan batasan diganti sesuai kondisi.

Detail metode dan batasan tersedia di halaman **Metodologi** pada aplikasi.

## Batasan penting

- Pemeriksaan fakta eksternal hanya mencakup klaim yang sudah diperiksa pihak lain; konten baru
  tidak akan punya catatan, dan ketiadaan catatan bukan bukti kebenaran.
- Pencarian MAFINDO memakai kata kunci pendek (endpoint `content` mencocokkan frasa utuh),
  sehingga klaim yang diparafrase tetap bisa terlewat. Kunci API MAFINDO dikirim di body
  form, jadi jaga kerahasiaan `backend/.env`.
- Status klaim berbasis AI adalah pembacaan model terhadap cuplikan sumber, bukan putusan fakta.
  Tanpa sitasi yang valid statusnya diturunkan menjadi “tidak cukup bukti”, dan setiap sitasi
  tetap wajib dibuka analis.
- URL media sosial (TikTok, Instagram, Facebook, X/Twitter) tidak di-ingest otomatis; tempelkan
  teks/caption-nya sebagai teks manual agar analisis berjalan.
- Leksikon dapat melewatkan sarkasme, kutipan berita, atau konteks budaya.
- Kesetaraan klaim dinilai model bahasa, sehingga temuan yang membahas klaim lain bisa lolos atau
  justru ditandai konteks secara keliru; analis tetap harus membuka tautan cek fakta.
- Kredibilitas penerbit berasal dari tabel heuristik; domain tak dikenal dinilai 0,50 dan domain
  pemerintah 0,80, sehingga penilaian bisa meleset untuk penerbit niche.
- Independensi dihitung per domain, sehingga sindikasi (satu rilis dikutip banyak media) dapat
  terhitung sebagai beberapa sumber independen.
- Kemiripan teks bukan bukti aktor yang sama (bisa karena sindikasi berita).
- Endpoint analisis sengaja terbuka untuk demo; gunakan autentikasi/token sebelum produksi.
- Keputusan akhir selalu berada pada analis manusia.

## Reset database

Hentikan server, hapus `backend/kartika_intel.db`, lalu jalankan `manage.py runserver` lagi.
Migrasi berjalan otomatis dan database dimulai kosong tanpa data contoh.

## Langkah berikutnya

1. Pakai LLM untuk merangkum bukti EBDE dan menyusun narasi analis (verdict tetap ditetapkan
   EBDE, bukan oleh model bahasa).
2. Proteksi API dengan token/session auth dan peran analis/supervisor.
3. Impor batch CSV/JSON untuk metadata akun dan waktu unggah.
4. Ekspor laporan investigasi (PDF/DOCX) dan notifikasi klaster baru.
5. Deployment produksi: `DEBUG=false`, `collectstatic`, WhiteNoise/Gunicorn, PostgreSQL.
