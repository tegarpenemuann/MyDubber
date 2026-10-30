<div align="center">
  <img src="docs/logo.svg" alt="Logo MyDubber" width="620">
</div>

<h1 align="center">MyDubber</h1>

<p align="center">
  <strong>Ubah video MP4 bersuara menjadi video dubbing Bahasa Indonesia — lokal, di CPU, tanpa cloud.</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB">
  <img alt="Redis via Docker" src="https://img.shields.io/badge/redis%20via-docker-2496ED">
  <img alt="CPU only" src="https://img.shields.io/badge/CPU-only-06B6D4">
  <img alt="License: attribution required" src="https://img.shields.io/badge/license-attribution%20required-10B981">
</p>

<p align="center">
  <strong>Bahasa Indonesia</strong> · <a href="README.md">English</a>
</p>

MyDubber adalah layanan HTTP kecil yang mengubah video berbahasa Inggris menjadi
video dengan **suara Bahasa Indonesia**. Anda mengunggah satu MP4, lalu menerima
satu MP4 dengan gambar yang tidak berubah dan audio yang sudah diganti suara
Indonesia.

Semua berjalan di komputer Anda sendiri. Tanpa akun, tanpa API key, tanpa
mengunggah video ke layanan cloud, dan tanpa GPU.

> **Ini adalah backend service, bukan aplikasi desktop.** Anda memakainya lewat
> halaman web bernama Swagger UI, atau lewat `curl`. Tidak ada halaman login.

## Daftar isi

- [Apa masalah yang dipecahkan?](#apa-masalah-yang-dipecahkan)
- [Fitur](#fitur)
- [Cara kerjanya](#cara-kerjanya)
- [Demo: video pendek Inggris ke dubbing Indonesia](#demo-video-pendek-inggris-ke-dubbing-indonesia)
- [Mulai cepat](#mulai-cepat)
- [Menghentikan](#menghentikan)
- [Glosarium istilah](#glosarium-istilah)
- [Konfigurasi](#konfigurasi)
- [Model, suara, dan aset](#model-suara-dan-aset)
- [Pengujian](#pengujian)
- [Penggunaan offline](#penggunaan-offline)
- [Membersihkan data hasil proses](#membersihkan-data-hasil-proses)
- [Pemecahan masalah](#pemecahan-masalah)
- [Batasan dan keamanan](#batasan-dan-keamanan)
- [Struktur proyek](#struktur-proyek)
- [Kontribusi](#kontribusi)
- [Lisensi](#lisensi)

## Apa masalah yang dipecahkan?

| Masalah | Cara MyDubber membantu |
| --- | --- |
| Videonya berbahasa Inggris, tetapi penontonnya berbahasa Indonesia. | Ucapan ditranskrip, diterjemahkan, lalu diucapkan kembali dalam Bahasa Indonesia. |
| Alat dubbing cloud berbayar, punya batas, dan mengunggah video pribadi. | Semua berjalan lokal. Video Anda tidak pernah keluar dari komputer Anda. |
| Anda tidak punya GPU. | Whisper, Llama, dan Piper semuanya berjalan di CPU biasa. |
| Anda butuh fitur ini di dalam program lain. | Ini API HTTP sederhana dengan tugas asynchronous, jadi satu program bisa mengirim banyak video. |
| Anda ingin kualitas gambar asli tetap terjaga. | Video stream disalin, bukan di-render ulang. Hanya audio yang berubah. |

**Untuk siapa?** Guru, kreator konten, studio kecil, dan tim internal yang butuh
versi Bahasa Indonesia dari video berbahasa Inggris tanpa mengirimnya ke layanan
pihak ketiga.

## Fitur

- Unggah MP4 dan langsung dapat `task_id`. Proses berjalan di latar belakang.
- Pengenalan ucapan dengan faster-whisper `base`, CPU, INT8.
- Penerjemahan lokal dengan Ollama dan model `llama3.2`, GPU dimatikan.
- Sintesis suara Indonesia dengan voice Piper `id_ID-news_tts-medium`.
- Ucapan disesuaikan dengan timing segmen asli, jadi dubbing tetap sinkron dengan gambar.
- Video stream disalin dengan FFmpeg (`-c:v copy`), jadi tidak di-render ulang.
- Progres per milestone, hasil bisa diunduh, dan dukungan HTTP Range untuk video player.
- Bekerja sepenuhnya offline setelah unduhan aset sekali saja.

```text
Upload -> Redis/Celery -> FFmpeg -> Whisper -> Ollama -> Piper -> FFmpeg -> Download
```

## Cara kerjanya

Saat Anda mengunggah file, API menyimpannya dan memasukkan pekerjaan ke antrean.
Proses **worker** mengambil pekerjaan itu dan menjalankan lima langkah:

| Progres | Stage | Yang terjadi |
| --- | --- | --- |
| 10% | `extracted` | FFmpeg mengekstrak audio menjadi WAV mono 16 kHz. |
| 30% | `transcribed` | Whisper mengubah ucapan menjadi teks beserta timestamp. |
| 60% | `translated` | Ollama menerjemahkan setiap segmen ke Bahasa Indonesia. |
| 80% | `synthesized` | Piper mengucapkan setiap segmen dalam Bahasa Indonesia, lalu segmen disusun menjadi satu trek audio. |
| 100% | `completed` | FFmpeg menggabungkan video asli dengan audio baru dan menerbitkan hasilnya. |

Progres berbasis **milestone**. Ini bukan perkiraan waktu, dan bisa melompat dari
30 langsung ke 60. Penerjemahan berjalan saat progres masih 30%; sintesis suara
berjalan saat masih 60%. Angka yang belum berubah tidak selalu berarti task macet.

## Demo: video pendek Inggris ke dubbing Indonesia

> **Penafian**
>
> - Tidak ada video contoh di repository ini. Gunakan hanya klip milik Anda
>   sendiri atau yang Anda punya izin untuk memprosesnya.
> - Terjemahan mesin dan suara sintetis tidak sempurna. Selalu periksa hasilnya
>   sebelum dipublikasikan.
> - Audio asli diganti, termasuk musik latar dan efek suara. Tidak ada lip-sync,
>   tidak ada voice cloning, dan tidak ada pemisahan pembicara.
> - Jangan gunakan MyDubber untuk mendubbing konten yang tidak boleh Anda salin
>   atau ubah.

Uji coba pertama yang baik adalah klip bahasa Inggris yang pendek:

1. Siapkan MP4 **10 sampai 30 detik** dengan video H.264 dan audio AAC.
   Pastikan ada orang yang benar-benar berbicara.
2. Unggah video tersebut (lihat [langkah 7](#7-dubbing-video-pertama)).
3. Perhatikan tahapnya: `extracted` → `transcribed` → `translated` → `synthesized` → `completed`.
4. Buka `download_url`. Anda sekarang punya video yang sama dengan suara Bahasa Indonesia.

Waktu proses bergantung pada CPU, kepadatan ucapan, pemuatan model, dan panjang
video. Penerjemahan di CPU dapat lebih lama daripada tahap lain; tidak ada
jaminan waktu selesai yang tetap.

## Mulai cepat

Yang dibutuhkan: Docker Desktop, Ollama dengan model `llama3.2`, Python 3.10+,
dan FFmpeg (di Windows dipasang otomatis). Disarankan RAM 16 GB dan disk ±3 GB.

Langkah 1–3 hanya sekali per komputer. Langkah 4–7 diulang setiap kali memakai
MyDubber.

### 1. Pasang Docker

Pasang [Docker Desktop](https://www.docker.com/products/docker-desktop/), buka,
lalu tunggu sampai statusnya running. Docker hanya dipakai untuk Redis.

```bash
docker --version
docker compose version
```

### 2. Pasang Ollama dan model

Pasang [Ollama](https://ollama.com/download), lalu unduh model penerjemah:

```bash
ollama --version
ollama pull llama3.2      # sekitar 2 GB, sekali saja
ollama list               # harus ada llama3.2
```

Aplikasi Ollama harus tetap berjalan saat MyDubber dipakai. Di Windows cukup buka
aplikasi desktopnya; kalau memakai versi CLI, jalankan `ollama serve` di terminal
terpisah.

### 3. Siapkan project

```powershell
# Windows PowerShell
git clone https://github.com/tegarpenemuann/MyDubber.git
cd MyDubber
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.prepare_local --download --skip-services
```

```bash
# Linux
git clone https://github.com/tegarpenemuann/MyDubber.git
cd MyDubber
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
sudo apt-get install ffmpeg
python -m scripts.prepare_local --download --skip-services
```

Skrip terakhir mengunduh model Whisper, voice Piper, dan aset Swagger UI. Di
Windows skrip itu juga memasang FFmpeg portable di `tools/ffmpeg/bin`. Hasil yang
benar menampilkan `All local assets ready.` dan selesai tanpa error.
`--skip-services` memeriksa aset lokal tanpa mengharuskan Redis atau Ollama
sudah berjalan.

**Jangan lanjut jika unduhan gagal atau terhenti.** Atasi error yang muncul,
lalu jalankan ulang perintah unduhan yang sama; file yang sudah ada dilewati.
Model diunduh sebelum aset Swagger, jadi setup yang terhenti bisa membuat
`tools/swagger` belum tersedia. API tetap bisa berjalan, tetapi `/docs` kosong
karena JavaScript dan CSS lokalnya belum ada. Pertahankan folder `tools/`
setelah setup; aset ini tidak disertakan di Git dan tidak diunduh oleh API.

### 4. Nyalakan Redis

Terminal 1, dari folder project:

```bash
docker compose up -d
docker compose ps      # STATUS harus healthy
```

Redis hanya mendengarkan di `127.0.0.1:6379`. Datanya disimpan di volume
`mydubber_redis_data`, jadi antrean tidak hilang saat container dihentikan.

### 5. Nyalakan worker

Terminal 2, dari folder project. Terminal ini menjalankan pipeline dubbing dan
menampilkan progres setiap video.

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe -m celery -A app.celery_utils:celery_app worker --loglevel=info --pool=solo --concurrency=1
```

```bash
# Linux
source .venv/bin/activate
python -m celery -A app.celery_utils:celery_app worker --loglevel=info --pool=prefork --concurrency=1
```

Tanda siap: `celery@<nama-mesin> ready.` Biarkan terminal ini terbuka.

### 6. Nyalakan API dan Swagger

Terminal 3, dari folder project. Periksa aset lokal terlebih dahulu:

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe -m scripts.prepare_local --skip-services
```

```bash
# Linux (virtual environment aktif)
python -m scripts.prepare_local --skip-services
```

Lanjutkan hanya jika muncul `All local assets ready.` dan perintah selesai
tanpa error. Jika ada aset yang hilang, ulangi perintah unduhan di langkah 3.
Setelah itu jalankan API:

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
# Linux
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Tanda siap: `Uvicorn running on http://127.0.0.1:8000`. Buka
**http://127.0.0.1:8000/docs** di browser; itulah Swagger UI.

> Port terpakai? Ganti `--port 8000` menjadi `--port 8001`, lalu buka
> `http://127.0.0.1:8001/docs`.

Swagger harus menampilkan **POST /api/v1/dubbing/tasks** dan
**GET /api/v1/dubbing/tasks/{task_id}**. Jika halaman kosong, periksa
`http://127.0.0.1:8000/docs-assets/swagger-ui-bundle.js` dan
`http://127.0.0.1:8000/docs-assets/swagger-ui.css`; keduanya harus merespons HTTP
`200`. Respons HTTP `404` atau `500` berarti aset belum tersaji dengan benar.
Periksa log API dan ulangi langkah 3 jika file hilang, lalu tekan **Ctrl+F5**
di `/docs`. Respons `/openapi.json` yang berhasil saja tidak membuktikan
JavaScript dan CSS Swagger sudah siap. Sesuaikan port pada URL jika diubah.

### 7. Dubbing video pertama

1. Buka **http://127.0.0.1:8000/docs**.
2. Buka **POST /api/v1/dubbing/tasks** → **Try it out** → pilih file MP4 →
   **Execute**. Respons `202` berarti tugas masuk antrean, bukan selesai.
3. Salin `task_id`, lalu buka **GET /api/v1/dubbing/tasks/{task_id}** →
   **Try it out** → tempel `task_id` → **Execute** setiap 5–10 detik.
4. Saat `status` menjadi `SUCCESS`, buka `download_url` untuk memutar atau
   mengunduh hasilnya.

```json
{
  "task_id": "c289faab-d38d-401f-9f22-9d028bbca925",
  "status": "SUCCESS",
  "progress": 100,
  "stage": "completed",
  "download_url": "/outputs/c289faab-d38d-401f-9f22-9d028bbca925.mp4",
  "error": null
}
```

### Alur yang sama dengan curl

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dubbing/tasks -F "file=@/path/to/video.mp4"
curl http://127.0.0.1:8000/api/v1/dubbing/tasks/<task_id>
```

Di Windows PowerShell, gunakan `curl.exe` alih-alih `curl`.

### Arti status

| Status | Arti |
| --- | --- |
| `PENDING` | Tugas upload sedang menunggu worker. ID tidak dikenal atau kedaluwarsa tanpa file tugas lokal mengembalikan HTTP `404`; gunakan `status_url` dari respons upload Anda, bukan ID contoh. |
| `STARTED` | Worker sudah mengambil tugas. |
| `PROGRESS` | Sedang berjalan; lihat `progress` dan `stage`. |
| `SUCCESS` | Selesai; `download_url` tersedia. |
| `FAILURE` / `REVOKED` | Gagal atau dibatalkan; periksa log worker. |

Progres berbasis milestone (10 ekstrak, 30 transkrip, 60 terjemah, 80 sintesis,
100 gabung), bukan perkiraan waktu.

### Error saat upload

| Kode | Arti |
| --- | --- |
| `400` | File kosong. |
| `413` | Melebihi batas upload (default 500 MiB). |
| `415` | Ekstensi bukan `.mp4`. |
| `422` | Request tidak valid, atau `task_id` bukan UUID. |
| `503` | Redis tidak bisa dihubungi. |

## Menghentikan

Hentikan dengan urutan **API → worker → Redis** supaya tidak ada proses yang
tertinggal di background.

**1. Hentikan API dan worker.** Klik terminalnya, tekan `Ctrl+C`, lalu tunggu
sampai prompt kembali. Jika terminal ditutup dengan tombol X, prosesnya bisa
tetap hidup; hentikan paksa dengan:

```powershell
# Windows
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'celery|uvicorn' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

```bash
# Linux
pkill -f "celery -A app.celery_utils"
pkill -f "uvicorn app.main:app"
```

**2. Hentikan Redis.**

```bash
docker compose stop      # container berhenti, data antrean tetap tersimpan
```

**3. Pastikan tidak ada yang tersisa.**

```bash
docker compose ps        # tidak boleh ada status Up
Get-Process python       # tidak boleh ada proses worker/API
ollama ps                # model ter-unload otomatis setelah 5 menit idle
```

**4. Opsional.** Hapus container dengan `docker compose down` (data tetap) atau
`docker compose down -v` (data antrean ikut hilang). Untuk mengosongkan memori
segera, jalankan `ollama stop llama3.2`. Untuk mematikan Docker sepenuhnya,
jalankan `docker desktop stop`.

Untuk menjalankan lagi: `docker compose start`, lalu ulangi langkah 5 dan 6.

## Glosarium istilah

| Istilah | Arti sederhana |
| --- | --- |
| **API** | Cara program saling berkomunikasi lewat HTTP. |
| **Endpoint** | Satu URL yang mengerjakan satu hal, misalnya `/api/v1/dubbing/tasks`. |
| **Request / response** | Yang Anda kirim, dan yang dikembalikan server. |
| **JSON** | Format teks untuk respons, seperti `{"status": "SUCCESS"}`. |
| **Task** | Satu pekerjaan dubbing, ditandai dengan `task_id` (UUID). |
| **Queue / antrean** | Barisan tunggu pekerjaan. Redis menyimpan antrean ini. |
| **Worker** | Program latar belakang yang mengambil pekerjaan dari antrean dan mengerjakannya. |
| **Polling** | Bertanya ke server "sudah selesai belum?" berulang kali. |
| **Container** | Lingkungan kecil dan terisolasi yang menjalankan satu service. |
| **Image** | Template tersimpan yang dipakai untuk membuat container. |
| **Volume** | Penyimpanan yang tetap ada saat container dihapus. |
| **Port** | Angka yang menandai service di sebuah mesin, misalnya `8000`. |
| **Swagger UI** | Halaman web di `/docs` tempat Anda bisa mencoba API dengan klik. |

## Konfigurasi

Salin `.env.example` menjadi `.env`. Semua pengaturan aplikasi memakai prefix
`MYDUBBER_`. API dan worker harus memakai konfigurasi dan folder penyimpanan
yang sama.

`.env` dibaca oleh API dan worker yang berjalan native. `docker-compose.yml`
hanya berisi Redis dan tidak memakai variabel aplikasi; ubah port Redis di file
itu bila 6379 sudah terpakai.

Tabel berikut menjelaskan semua pengaturan aplikasi:

| Variabel | Default | Fungsi |
| --- | --- | --- |
| `MYDUBBER_STORAGE_DIR` | `./storage` | Tempat upload, file sementara, dan hasil disimpan. |
| `MYDUBBER_REDIS_URL` | `redis://127.0.0.1:6379/0` | Broker Celery. |
| `MYDUBBER_REDIS_RESULT_URL` | `redis://127.0.0.1:6379/1` | Result backend Celery. |
| `MYDUBBER_OLLAMA_URL` | `http://127.0.0.1:11434/api/generate` | Endpoint generasi Ollama. |
| `MYDUBBER_OLLAMA_MODEL` | `llama3.2` | Model penerjemah. |
| `MYDUBBER_WHISPER_MODEL_DIR` | `./models/whisper-base` | Folder model Whisper lokal. |
| `MYDUBBER_PIPER_MODEL_PATH` | `./models/piper/id_ID-news_tts-medium.onnx` | Voice Piper lokal. |
| `MYDUBBER_CPU_THREADS` | `4` | Pengaturan thread FFmpeg, Whisper, dan Ollama. Rentang 1–16; tidak mengatur sesi ONNX Piper. |
| `MYDUBBER_MAX_UPLOAD_MB` | `500` | Batas upload dalam MiB. |
| `MYDUBBER_RESULT_EXPIRES` | `86400` | Berapa lama metadata tugas disimpan di Redis, dalam detik. |
| `MYDUBBER_OLLAMA_TIMEOUT` | `300` | Timeout per request penerjemahan, dalam detik. |
| `MYDUBBER_FFMPEG_TIMEOUT` | `1800` | Timeout per panggilan FFmpeg/FFprobe, dalam detik. |
| `MYDUBBER_FFMPEG_BINARY` | otomatis | Menimpa path executable FFmpeg. |
| `MYDUBBER_FFPROBE_BINARY` | otomatis | Menimpa path executable FFprobe. |
| `MYDUBBER_CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Origin browser yang diizinkan, sebagai array JSON. |

Path relatif dihitung dari working directory saat ini. API dan worker memblokir
koneksi ke host non-loopback, jadi Redis dan Ollama harus berjalan di `localhost`.

## Model, suara, dan aset

| Komponen | Yang dipakai MyDubber | Sumber dan ketentuan |
| --- | --- | --- |
| Pengenalan ucapan | faster-whisper `base`, CPU, INT8 | [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base) |
| Penerjemahan | `llama3.2` lewat Ollama, temperature 0, GPU dimatikan | [Ollama library](https://ollama.com/library/llama3.2) — ketentuan Meta Llama 3.2 |
| Suara Indonesia | `id_ID-news_tts-medium` | [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/id/id_ID/news_tts/medium) |
| Media | FFmpeg dan FFprobe | Build Windows dari [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), atau package OS Anda |
| Dokumentasi API | Swagger UI 5.17.14, disimpan lokal | [swagger-ui-dist](https://www.npmjs.com/package/swagger-ui-dist) — Apache-2.0 |

### Tentang suara Bahasa Indonesia

| Properti | Nilai |
| --- | --- |
| Voice ID | `id_ID-news_tts-medium` |
| Bahasa | Indonesia (`id_ID`), satu speaker |
| Kualitas | medium, 22.050 Hz (pipeline me-resample ke 16 kHz mono) |
| Phonemizer | eSpeak NG, voice `id`, berjalan lokal |
| Data latih | `news_tts`. Model card menautkan dataset dan menulis "License: See URL". |
| Lisensi repository | Repository Piper voices menyatakan MIT. Ketentuan dataset bisa berbeda. |

File voice diunduh sekali oleh `scripts/prepare_local.py` lalu dimuat dari disk.
Tidak ada yang diunduh saat runtime.

## Pengujian

### Unit test (tanpa service)

Unit test memakai mock untuk Redis, Ollama, Whisper, Piper, dan pemrosesan media.
Anda bisa menjalankannya di mesin mana pun, tanpa model atau container.

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
python -m pip check
```

Pemeriksaan ini didukung di Windows dan Linux dengan Python 3.10 dan 3.12.

### Integration test dengan video asli

Test ini mengunggah file asli lewat API dan memeriksa seluruh pipeline. Test ini
butuh Redis, Ollama, worker, API, dan semua aset lokal.

```bash
python -m scripts.test_local /path/to/sample-en.mp4
```

Gunakan klip bahasa Inggris pendek milik Anda. Test ini memeriksa:

- Swagger UI dan aset lokalnya bisa dimuat,
- upload diterima dengan HTTP 202,
- tugas mencapai `SUCCESS` dengan `progress: 100`,
- durasi output sama dengan sumber dalam selisih 0,25 detik,
- bitstream video tidak berubah (gambar tidak di-render ulang),
- audio tidak hening,
- byte yang diunduh sama dengan file hasil,
- request HTTP Range mengembalikan `206`,
- file upload dan file kerja sementara dihapus.

Laporan disimpan di `storage/e2e-report.json`.

## Penggunaan offline

Setelah instalasi sekali jalan, MyDubber bekerja tanpa internet:

- Whisper memuat model lokal dan tidak pernah mengunduh ulang.
- Piper memuat voice dan phonemizer dari disk. Tidak ada fallback TTS online.
- URL Redis dan Ollama harus mengarah ke alamat loopback.
- API dan worker memblokir koneksi socket non-loopback serta mematikan unduhan
  dan telemetri Hugging Face.
- FFmpeg hanya menerima protokol lokal `file` dan `pipe`.
- Aset Swagger disajikan secara lokal. Validator eksternal dimatikan.
- Container Redis memakai image yang sudah ada di mesin; `docker compose` tidak
  melakukan pull ulang saat service dijalankan kembali.

Pemeriksaan Python berlaku di level aplikasi, bukan firewall sistem. Untuk mesin
tanpa internet, pindahkan paket Python, model Whisper/Piper, FFmpeg, dan image
Redis (`docker save`/`docker load`) lewat media lokal. Ollama beserta model
`llama3.2` juga harus sudah terpasang sebelum mesin diputus dari jaringan.

## Membersihkan data hasil proses

Kode sumber tidak menyertakan video input, contoh hasil dubbing, laporan
integration test, atau cache runtime. Pemakaian normal tetap melalui upload API.

Hentikan API dan worker serta tutup pemutar video sebelum menghapus berkas.
Antrean dan metadata tugas disimpan di volume Redis `mydubber_redis_data`.
Untuk menghapusnya sekaligus, jalankan:

```bash
docker compose down --volumes
```

Perintah ini destruktif dan tidak dapat dibatalkan.

Untuk instalasi **native** dengan path storage default, hentikan API dan worker,
lalu hapus `storage/` dari folder utama repository:

```powershell
if (Test-Path storage) { Remove-Item -LiteralPath storage -Recurse -Force }
```

Di Linux/macOS, gunakan `rm -rf -- storage`. Jika memakai lokasi storage lain,
bersihkan lokasi tersebut. Metadata Redis native disimpan terpisah. API membuat
ulang folder upload, temp, dan output pada startup berikutnya.

Pertahankan `models/` dan `tools/` untuk operasi offline. `.venv/` hanya diperlukan
untuk instalasi native atau pengembangan. Model `llama3.2` dikelola Ollama di
folder model miliknya sendiri, di luar repository ini.

## Pemecahan masalah

| Gejala | Penyebab yang mungkin | Solusi |
| --- | --- | --- |
| Swagger `/docs` kosong | JavaScript/CSS Swagger lokal belum ada, sering karena setup terhenti. | Ulangi perintah unduhan di [langkah 3](#3-siapkan-project), tunggu `All local assets ready.` tanpa error, pastikan `/docs-assets/swagger-ui-bundle.js` dan `/docs-assets/swagger-ui.css` merespons `200`, lalu tekan Ctrl+F5. |
| Tugas terus `PENDING` | Worker tidak berjalan, atau memakai Redis berbeda. | Jalankan worker. Pastikan kedua proses memakai `MYDUBBER_REDIS_URL` yang sama. |
| Upload mengembalikan `503` | Redis tidak bisa dihubungi. | Jalankan Redis, lalu cek `docker compose ps`. |
| Polling mengembalikan `503` | Result backend tidak bisa dihubungi. | Periksa `MYDUBBER_REDIS_RESULT_URL`. |
| Tugas berakhir `FAILURE` dengan "model is not available" | File model belum ada. | Jalankan `python -m scripts.prepare_local --download`. |
| Tugas berakhir `FAILURE` dengan "Program not found" | FFmpeg tidak terpasang atau tidak ada di `PATH`. | Pasang FFmpeg, atau set `MYDUBBER_FFMPEG_BINARY`. |
| "No speech was detected" | Video berisi musik tanpa suara, atau ucapannya terlalu pelan. | Gunakan klip dengan ucapan yang jelas. |
| Upload mengembalikan `415` | Nama file bukan `.mp4`. | Ganti nama atau remux file ke MP4 dulu. |
| Port 8000 sudah dipakai | Program lain memakai port itu. | Jalankan uvicorn dengan `--port 8001`. |
| Port 6379 sudah dipakai | Sudah ada Redis lain yang berjalan. | Hentikan Redis itu, atau ubah port di `docker-compose.yml` dan kedua URL Redis. |
| `prepare_local` gagal di pemeriksaan Ollama | Ollama belum jalan, atau model `llama3.2` belum diunduh. | Jalankan `ollama serve`, lalu `ollama pull llama3.2`. |
| Celery gagal di Windows | Pool default tidak didukung. | Gunakan `--pool=solo` seperti contoh di atas. |
| Run pertama sangat lambat | Model sedang dimuat untuk pertama kali. | Tunggu. Run berikutnya memakai model yang sudah dimuat. |
| Output tidak bisa diputar di beberapa player | `-c:v copy` mempertahankan codec yang tidak didukung player tersebut. | Gunakan MP4 H.264/AAC standar. |

## Batasan dan keamanan

- **Hanya untuk penggunaan lokal yang tepercaya.** Tidak ada autentikasi, rate
  limiting, batas durasi, atau kuota penyimpanan. Jangan mengekspos API, Redis,
  atau Ollama ke internet.
- CORS bukan kontrol akses.
- Batas upload diperiksa setelah multipart diurai. Tambahkan batas ukuran body
  di proxy jika Anda menaruh proxy di depan API.
- Audio asli diganti, termasuk musik latar. Tidak ada voice cloning, diarisasi
  pembicara, pemisahan latar, atau lip-sync.
- Ucapan bisa dipercepat atau ditambah jeda agar sesuai timestamp asli.
  Terjemahan dan istilah teknis perlu diperiksa manusia.
- Codec MP4 yang tidak kompatibel bisa membuat penggabungan video gagal.
- File upload dan file sementara dihapus setelah sukses atau gagal. Jika worker
  dimatikan paksa, file atau tugas bisa tertinggal di status `STARTED`.
- Hasil tetap tersimpan di disk sampai Anda menghapusnya. Metadata tugas
  kedaluwarsa setelah 24 jam secara default, tetapi file videonya tidak.
- Tugas tidak diulang otomatis. Periksa log worker setelah `FAILURE`.
- Biarkan concurrency di 1 pada mesin dengan RAM terbatas. Whisper dan Piper
  di-cache per proses worker, dan Ollama menyimpan model selama lima menit.

## Struktur proyek

```text
app/
  main.py           Aplikasi FastAPI, endpoint upload dan status
  config.py         Pengaturan dengan prefix MYDUBBER_
  celery_utils.py   Broker dan result backend Celery
  offline.py        Kebijakan jaringan loopback-only
  tasks.py          Pipeline dubbing lima tahap
scripts/
  prepare_local.py  Unduhan aset sekali jalan dan verifikasi lokal
  test_local.py     Integration test dengan media asli
tests/
  test_backend.py   Unit test dan test kontrak API
docs/
  logo.svg          Logo proyek
docker-compose.yml  Satu service: Redis untuk antrean dan metadata tugas
```

`models/` dan `tools/` adalah aset lokal yang tidak masuk version control.
`storage/` dibuat saat runtime dan diabaikan Git. Model `llama3.2` disimpan Ollama
di folder model miliknya, di luar repository. Folder `video/` tidak diperlukan.
Jangan mempublikasikan media pribadi, laporan hasil, atau bobot model bersama kode
sumber.

## Kontribusi

Lihat [CONTRIBUTING.md](CONTRIBUTING.md) untuk setup pengembangan, pemeriksaan,
dan aturan pull request. Singkatnya: tetap CPU-only, tetap offline setelah
instalasi, dan jangan menambahkan unduhan runtime atau fallback cloud.

## Lisensi

MyDubber dirilis di bawah **MyDubber License**: Anda boleh memakai, mengubah, dan
menyebarluaskannya, termasuk untuk komersial, selama Anda menyertakan notice hak
cipta dan memberikan kredit yang jelas kepada **MyDubber contributors**. Lihat
[LICENSE](LICENSE).

Lisensi ini hanya mencakup kode sumber di repository ini. Perangkat lunak dan aset
pretrained pihak ketiga tetap memakai ketentuannya masing-masing. Secara khusus,
periksa:

- lisensi GPL-3.0 Piper serta model card dan ketentuan dataset voice Piper,
- ketentuan model Llama 3.2,
- lisensi versi Redis yang Anda pakai,
- lisensi build FFmpeg Anda (LGPL atau GPL tergantung build),
- lisensi Apache-2.0 Swagger UI.

Memasang sebuah dependency tidak membuat asetnya menjadi bagian dari lisensi
MyDubber.
