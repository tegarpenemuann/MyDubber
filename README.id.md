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

> **Ini adalah aplikasi web lokal sekaligus API HTTP.** Buka dashboard di
> **http://127.0.0.1:8000/** untuk mengunggah, memantau progres, dan memutar
> hasil, atau pakai Swagger UI di **/docs** dan `curl`. Tidak ada halaman login.

## Daftar isi

- [Apa masalah yang dipecahkan?](#apa-masalah-yang-dipecahkan)
- [Fitur](#fitur)
- [Cara kerjanya](#cara-kerjanya)
- [Demo: video pendek Inggris ke dubbing Indonesia](#demo-video-pendek-inggris-ke-dubbing-indonesia)
- [Video berdurasi panjang](#video-berdurasi-panjang)
- [Mulai cepat](#mulai-cepat)
- [Dashboard web](#dashboard-web)
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
- Mendukung rekaman panjang: video dua jam dapat diproses, dengan batas yang bisa diatur sampai enam jam.
- Pengenalan ucapan dengan faster-whisper `base`, CPU, INT8.
- Penerjemahan lokal dengan Ollama dan model `llama3.2`, GPU dimatikan dan dibatch untuk transkrip panjang.
- Sintesis suara Indonesia dengan voice Piper `id_ID-news_tts-medium`.
- Ucapan disesuaikan dengan timing segmen asli memakai `length_scale` Piper, jadi dubbing tetap sinkron dengan gambar.
- Checkpoint membuat task yang terputus bisa dilanjutkan tanpa mengulang transkripsi dan batch terjemahan yang sudah selesai.
- Video stream disalin dengan FFmpeg (`-c:v copy`), jadi tidak di-render ulang.
- Progres per milestone, hasil bisa diunduh, dan dukungan HTTP Range untuk video player.
- Dashboard lokal dengan upload drag-and-drop beberapa file, progres langsung
  lewat Server-Sent Events, riwayat yang tersimpan, play/download, serta tema
  terang atau gelap dalam Bahasa Indonesia dan Inggris.
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
| 10–29% | `transcribing` | Whisper mengubah ucapan menjadi teks beserta timestamp. |
| 30% | `transcribed` | Transkrip disimpan sebagai checkpoint. |
| 30–59% | `translating` | Ollama menerjemahkan segmen secara batch ke Bahasa Indonesia. |
| 60% | `translated` | Setiap segmen sudah punya terjemahan Bahasa Indonesia. |
| 60–79% | `synthesizing` | Piper mengucapkan setiap segmen dan timeline disusun pada sample rate voice. |
| 80% | `synthesized` | Timeline dubbing sudah sama persis dengan durasi video. |
| 100% | `completed` | FFmpeg menggabungkan video asli dengan audio baru dan menerbitkan hasilnya. |

Progres berbasis **milestone** dengan persentase di dalam tahap. Ini bukan
perkiraan waktu, jadi angkanya bisa tidak berubah untuk sementara saat tahap
panjang berjalan. Perubahan tahap selalu memperbarui progres; pembaruan di
tengah tahap dibatasi menjadi satu setiap beberapa detik agar Redis tidak
dibanjiri.

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

## Video berdurasi panjang

Rekaman dua jam didukung di CPU. Perhatikan hal-hal berikut:

- Batas durasi default adalah **6 jam** (`MYDUBBER_MAX_MEDIA_HOURS`). File yang
  lebih panjang langsung gagal dengan pesan yang jelas.
- Batas upload default adalah **4096 MiB**. Naikkan `MYDUBBER_MAX_UPLOAD_MB` di
  `.env` untuk file yang lebih besar; API dan worker harus memakai nilai yang
  sama.
- Perkirakan sekitar **1–1,5 jam** pemrosesan untuk video 1080p dua jam pada CPU
  4 thread dengan model Whisper base. Ini perkiraan, bukan jaminan.
- Ruang disk kosong di drive penyimpanan minimal **dua kali ukuran video ditambah
  0,35 GB per jam video** untuk timeline sementara. Upload terlebih dahulu
  ditampung di temporary directory sistem, jadi drive tersebut juga butuh ruang
  kosong.
- Worker harus tetap berjalan selama seluruh proses. Pekerjaan dua jam tidak
  atomik: jika worker berhenti, upload dan checkpoint JSON disimpan selama
  `MYDUBBER_RESULT_EXPIRES` detik (default 24 jam).
- Setelah gagal, masukkan ulang **task ID yang sama** alih-alih mengunggah lagi.
  Transkripsi dan batch terjemahan yang sudah selesai akan dipakai ulang, dan
  sintesis dimulai dari timeline terakhir yang selesai.

Masukkan ulang task yang gagal dari folder proyek saat Redis dan worker
berjalan:

```bash
python -c "from app.tasks import dub_video; dub_video.apply_async(args=['<task_id>'], task_id='<task_id>', retry=False)"
```

Status API untuk task tersebut akan berubah dari `FAILURE` kembali ke `PROGRESS`.
Upload dan checkpoint lama yang tidak pernah dimasukkan ulang akan dihapus
otomatis setelah `MYDUBBER_RESULT_EXPIRES` detik.

## Mulai cepat

Yang dibutuhkan: Docker Desktop, Ollama dengan model `llama3.2`, Python 3.10+,
dan FFmpeg (di Windows dipasang otomatis). GNU Make opsional dan mengaktifkan
perintah cepat di bawah. Disarankan RAM 16 GB dan disk ±3 GB.

Langkah 1–3 hanya sekali per komputer. Langkah 4–7 diulang setiap kali memakai
MyDubber.

### Cara cepat dengan Make

Jika GNU Make sudah terpasang, dua perintah menggantikan langkah 1–6:

```bash
make setup   # sekali: buat .venv, install dependensi, salin .env, unduh aset
make up      # nyalakan Redis, API, dan worker
```

Docker Desktop harus berjalan. Ollama tidak pernah dinyalakan atau dimatikan oleh
target ini, jadi instans host eksternal dipakai langsung. `make up` mencetak URL
Swagger dan menulis log API serta worker ke `storage/logs/`.

| Perintah | Fungsi |
| --- | --- |
| `make setup` | Buat `.venv`, install dependensi, salin `.env.example`, unduh model dan tools. |
| `make up` | Nyalakan Redis, API, dan worker di background. |
| `make stop` | Hentikan API dan worker; Redis tetap berjalan. |
| `make down` | Hentikan API, worker, dan Redis. Volume Redis dan hasil tetap disimpan. |
| `make status` | Tampilkan status proses, API, Redis, dan Ollama. |
| `make doctor` | Periksa prasyarat, aset lokal, port, dan Ollama. |
| `make logs` | Ikuti log API dan worker; `make logs-api` atau `make logs-worker` untuk satu proses. |
| `make test` / `make lint` | Jalankan unit test atau pemeriksaan gaya kode. |
| `make e2e VIDEO=/path/to/video.mp4` | Jalankan integration test dengan video asli. |

Gunakan `make up PORT=8001` jika port 8000 dipakai, dan `make logs LINES=200`
untuk riwayat lebih banyak. Menghentikan stack saat dubbing berjalan akan
memutus task tersebut; upload dan checkpoint JSON tetap disimpan untuk requeue.

Langkah manual di bawah melakukan hal yang sama tanpa Make.

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
**http://127.0.0.1:8000/** untuk dashboard, atau
**http://127.0.0.1:8000/docs** untuk Swagger UI.

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

Dashboard di **http://127.0.0.1:8000/** adalah cara termudah: tarik MP4 ke drop
zone dan lihat setiap tahap diperbarui langsung. Alur Swagger di bawah setara
dengan versi API saja.

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

Progres berbasis milestone (10 ekstrak, 10–29 transkrip, 30–59 terjemah, 60–79
sintesis, 80 gabung), bukan perkiraan waktu.

### Error saat upload

| Kode | Arti |
| --- | --- |
| `400` | File kosong. |
| `413` | Melebihi batas upload (default 4096 MiB). |
| `415` | Ekstensi bukan `.mp4`. |
| `422` | Request tidak valid, atau `task_id` bukan UUID. |
| `503` | Redis tidak bisa dihubungi. |

## Dashboard web

Dashboard disajikan oleh proses FastAPI yang sama di
**http://127.0.0.1:8000/** (atau `make open`). Isinya HTML, CSS, dan JavaScript
biasa tanpa langkah build dan tanpa CDN, jadi tetap bekerja offline seperti
bagian aplikasi lainnya.

- Tarik satu atau beberapa file MP4 ke drop zone. Upload dikirim satu per satu
  dan setiap file punya progres upload sendiri.
- Task yang menunggu dan berjalan diperbarui langsung lewat Server-Sent Events.
  Daftar dipulihkan dari disk saat halaman atau API dijalankan ulang.
- Filter task aktif, selesai, atau gagal, lalu cari berdasarkan nama file.
- Task yang selesai bisa diputar di dialog atau diunduh tanpa meninggalkan
  halaman.
- Antarmuka dua bahasa. Bahasa mengikuti browser (`id` menjadi Bahasa Indonesia,
  selain itu Inggris) dan pilihan bahasa serta tema terang/gelap diingat di
  `localStorage`.

Dashboard memakai endpoint berikut:

| Endpoint | Fungsi |
| --- | --- |
| `GET /api/v1/dubbing/config` | Batas ukuran upload dan durasi yang ditampilkan di UI. |
| `GET /api/v1/dubbing/tasks?limit=50` | Metadata task tersimpan, yang aktif lebih dulu. |
| `GET /api/v1/dubbing/events` | Stream SSE snapshot task (`tasks`) dan heartbeat 15 detik (`ping`). Tidak muncul di OpenAPI. |
| `POST /api/v1/dubbing/tasks` | Upload dan masukkan task ke antrean. |
| `GET /api/v1/dubbing/tasks/{task_id}` | Polling satu task. |
| `GET /outputs/{task_id}.mp4` | Putar atau unduh hasil. |

Metadata task disimpan di `storage/tasks/<task_id>.json` dan ditulis secara
atomik oleh API maupun worker. Maksimal 200 catatan disimpan, dan catatan tanpa
hasil dihapus setelah `MYDUBBER_RESULT_EXPIRES`. Video hasil tetap berada di
`storage/outputs/`.

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
| `MYDUBBER_MAX_UPLOAD_MB` | `4096` | Batas upload dalam MiB. |
| `MYDUBBER_MAX_MEDIA_HOURS` | `6` | Durasi video maksimum yang diterima, dalam jam. |
| `MYDUBBER_RESULT_EXPIRES` | `86400` | Berapa lama metadata tugas disimpan di Redis, dan berapa lama upload/checkpoint yang gagal disimpan, dalam detik. |
| `MYDUBBER_OLLAMA_TIMEOUT` | `300` | Timeout per request penerjemahan, dalam detik. |
| `MYDUBBER_FFMPEG_TIMEOUT` | `7200` | Timeout per panggilan FFmpeg/FFprobe, dalam detik. |
| `MYDUBBER_TRANSLATION_BATCH_CHARS` | `700` | Maksimum karakter transkrip per request Ollama. Set `0` untuk menerjemahkan satu segmen per request. |
| `MYDUBBER_TRANSLATION_BATCH_SEGMENTS` | `8` | Maksimum segmen per request Ollama. |
| `MYDUBBER_TRANSLATION_RETRIES` | `3` | Jumlah percobaan per request penerjemahan sebelum task gagal. |
| `MYDUBBER_PROGRESS_MIN_INTERVAL` | `5` | Jarak minimum dalam detik antar pembaruan progres di dalam tahap. |
| `MYDUBBER_TASK_VISIBILITY_TIMEOUT` | `43200` | Visibility timeout broker Redis. Harus lebih besar dari task terlama. |
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
| Kualitas | medium, 22.050 Hz (dipakai langsung untuk timeline dubbing) |
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

Timeout tunggu dihitung otomatis dari durasi video secara default. Gunakan
`--timeout` untuk menimpanya. Laporan disimpan di `storage/e2e-report.json`.

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
| `make: command not found` | GNU Make belum terpasang. | Ikuti langkah manual di [Mulai cepat](#mulai-cepat), atau pasang Make (misalnya `choco install make`). |
| `make up` bilang Docker belum siap | Docker Desktop mati atau masih starting. | Buka Docker Desktop, tunggu sampai running, lalu jalankan `make up` lagi. |
| `make up` bilang port 8000 dipakai | Ada API atau program lain di port itu. | Hentikan program tersebut, atau jalankan `make up PORT=8001` lalu buka URL baru. |
| `make up` memperingatkan Ollama tidak bisa dihubungi | Service Ollama eksternal belum berjalan. | Buka aplikasi Ollama atau jalankan `ollama serve`; unduh model dengan `ollama pull llama3.2`. |
| `make stop` tidak menghentikan proses | Proses dijalankan manual, di luar Makefile. | Hentikan di terminal asalnya, atau lewat Task Manager / `taskkill`. |
| Task panjang lama tertahan di 30% | Penerjemahan transkrip besar berat di CPU. | Tunggu, atau kurangi rebutan `MYDUBBER_CPU_THREADS` dengan menutup program lain. Periksa log worker untuk peringatan per batch. |
| Task panjang gagal setelah worker restart | Pekerjaan terputus, bukan dibatalkan. | Jalankan ulang Redis dan worker, lalu masukkan ulang task ID yang sama seperti di [Video berdurasi panjang](#video-berdurasi-panjang). |
| Video panjang mengembalikan `413` | File melebihi `MYDUBBER_MAX_UPLOAD_MB`. | Naikkan nilainya di `.env` untuk API dan worker. |
| "Not enough free disk space" | Drive penyimpanan tidak cukup untuk upload plus timeline sementara. | Kosongkan ruang, pindahkan `MYDUBBER_STORAGE_DIR` ke drive lain, atau perpendek video. |
| "configured limit is 6.0 hours" | Penjaga durasi menolak video. | Naikkan `MYDUBBER_MAX_MEDIA_HOURS` jika mesin mampu. |

## Batasan dan keamanan

- **Hanya untuk penggunaan lokal yang tepercaya.** Tidak ada autentikasi, rate
  limiting, atau kuota penyimpanan. Hanya batas durasi yang bisa diatur
  (`MYDUBBER_MAX_MEDIA_HOURS`) yang menjaga pemakaian sumber daya. Jangan
  mengekspos API, Redis, atau Ollama ke internet.
- CORS bukan kontrol akses.
- Ukuran upload diperiksa sedini mungkin, tetapi FastAPI tetap menampung body
  multipart ke temporary directory sistem sebelum API membacanya. Tambahkan batas
  ukuran body di proxy jika Anda menaruh proxy di depan API.
- Audio asli diganti, termasuk musik latar. Tidak ada voice cloning, diarisasi
  pembicara, pemisahan latar, atau lip-sync.
- Ucapan bisa dipercepat atau ditambah jeda agar sesuai timestamp asli.
  Terjemahan dan istilah teknis perlu diperiksa manusia.
- Codec MP4 yang tidak kompatibel bisa membuat penggabungan video gagal.
- Task yang sukses menghapus upload dan file sementaranya. Task yang gagal
  menyimpan upload dan checkpoint JSON sampai `MYDUBBER_RESULT_EXPIRES` habis,
  supaya bisa dimasukkan ulang. Jika worker dimatikan paksa, file atau tugas bisa
  tertinggal di status `STARTED`.
- Hasil tetap tersimpan di disk sampai Anda menghapusnya. Metadata tugas
  kedaluwarsa setelah 24 jam secara default, tetapi file videonya tidak.
- Tugas tidak diulang otomatis. Masukkan ulang task ID yang sama setelah
  memeriksa log worker; checkpoint yang sudah selesai akan dipakai ulang.
- Biarkan concurrency di 1 pada mesin dengan RAM terbatas. Whisper dan Piper
  di-cache per proses worker, dan Ollama menyimpan model selama lima menit.

## Struktur proyek

```text
app/
  main.py           Aplikasi FastAPI, dashboard, endpoint upload, daftar, dan status
  config.py         Pengaturan dengan prefix MYDUBBER_
  celery_utils.py   Broker dan result backend Celery
  offline.py        Kebijakan jaringan loopback-only
  tasks.py          Pipeline dubbing, checkpoint, dan pelaporan progres
  task_store.py     Registry task JSON atomik yang dipakai API dan worker
  events.py         Broker Server-Sent Events untuk pembaruan dashboard
  web/
    index.html      Markup dashboard
    styles.css      Tema studio gelap dan terang
    app.js          Antrean upload, klien SSE, i18n, dan logika player
scripts/
  dev.py            Helper start, stop, status, dan log untuk Makefile
  prepare_local.py  Unduhan aset sekali jalan dan verifikasi lokal
  test_local.py     Integration test dengan media asli
tests/
  test_backend.py   Unit test dan test kontrak API
  test_task_store.py  Test registry task dan pemangkasan
  test_events.py    Test format SSE dan broker
  test_dev_script.py  Test untuk helper developer
docs/
  logo.svg          Logo proyek
Makefile            Start dan stop Redis, API, dan worker dengan satu perintah
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
