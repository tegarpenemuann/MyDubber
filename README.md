<div align="center">
  <img src="docs/logo.svg" alt="MyDubber logo" width="620">
</div>

<h1 align="center">MyDubber</h1>

<p align="center">
  <strong>English</strong> · <a href="README.id.md">Bahasa Indonesia</a>
</p>

<p align="center">
  <strong>Dub any spoken MP4 into Bahasa Indonesia — locally, on CPU, without the cloud.</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB">
  <img alt="Redis via Docker" src="https://img.shields.io/badge/redis%20via-docker-2496ED">
  <img alt="CPU only" src="https://img.shields.io/badge/CPU-only-06B6D4">
  <img alt="License: attribution required" src="https://img.shields.io/badge/license-attribution%20required-10B981">
</p>

MyDubber is a small HTTP service that turns a video with English speech into a
video with **Indonesian speech**. You upload one MP4. You get back one MP4 where
the picture is untouched and the audio has been replaced with a natural-sounding
Indonesian voice.

Everything runs on your own computer. No account, no API key, no upload to a
cloud service, and no GPU.

> **This is a local web app plus an HTTP API.** Open the dashboard at
> **http://127.0.0.1:8000/** to upload, watch progress, and play results, or use
> Swagger UI at **/docs** and `curl`. There is no login screen.

## Contents

- [What problem does it solve?](#what-problem-does-it-solve)
- [Features](#features)
- [How it works](#how-it-works)
- [Demo: English short to Indonesian dub](#demo-english-short-to-indonesian-dub)
- [Long videos](#long-videos)
- [Quick start](#quick-start)
- [Web dashboard](#web-dashboard)
- [Stopping](#stopping)
- [Plain-English glossary](#plain-english-glossary)
- [Configuration](#configuration)
- [Models, voices, and assets](#models-voices-and-assets)
- [Testing](#testing)
- [Offline use](#offline-use)
- [Cleaning generated data](#cleaning-generated-data)
- [Troubleshooting](#troubleshooting)
- [Limitations and security](#limitations-and-security)
- [Project layout](#project-layout)
- [Contributing](#contributing)
- [License](#license)

## What problem does it solve?

| Problem | How MyDubber helps |
| --- | --- |
| The video is in English, but the audience speaks Indonesian. | It transcribes the speech, translates it, and speaks the result in Indonesian. |
| Cloud dubbing tools are paid, have limits, and upload private video. | Everything runs locally. Your video never leaves your machine. |
| You do not have a GPU. | Whisper, Llama, and Piper all run on a normal CPU. |
| You need this inside another program. | It is a simple HTTP API with asynchronous tasks, so one program can send many videos. |
| You want to keep the original picture quality. | The video stream is copied, not re-encoded. Only the audio changes. |

**Who is it for?** Teachers, content creators, small studios, and internal teams
that need Indonesian versions of English videos without sending them to a
third-party service.

## Features

- Upload an MP4 and get a task ID immediately. Processing continues in the background.
- Handles long recordings: a two-hour video is supported, with a configurable limit of six hours.
- Speech recognition with faster-whisper `base`, CPU, INT8.
- Local translation with Ollama and the `llama3.2` model, GPU disabled and batched for long transcripts.
- Indonesian speech synthesis with Piper voice `id_ID-news_tts-medium`.
- Speech is fitted to the original segment timing with Piper `length_scale`, so the dub stays in sync with the picture.
- Checkpoints let an interrupted task resume without repeating transcription and finished translation batches.
- The video stream is copied with FFmpeg (`-c:v copy`), so it is not re-encoded.
- Progress updates by milestone, a downloadable result, and HTTP Range support for video players.
- A local dashboard with drag-and-drop multi-file upload, live progress over
  Server-Sent Events, persistent history, play/download, and light or dark themes
  in Indonesian and English.
- Works fully offline after a one-time asset download.

```text
Upload -> Redis/Celery -> FFmpeg -> Whisper -> Ollama -> Piper -> FFmpeg -> Download
```

## How it works

When you upload a file, the API saves it and puts a job in a queue. A **worker**
process picks up the job and runs five steps:

| Progress | Stage | What happens |
| --- | --- | --- |
| 10% | `extracted` | FFmpeg extracts the audio as 16 kHz mono WAV. |
| 10–29% | `transcribing` | Whisper turns the speech into text with timestamps. |
| 30% | `transcribed` | The transcript is stored as a checkpoint. |
| 30–59% | `translating` | Ollama translates the segments in batches into Indonesian. |
| 60% | `translated` | Every segment has an Indonesian translation. |
| 60–79% | `synthesizing` | Piper speaks each segment and the timeline is assembled at the voice sample rate. |
| 80% | `synthesized` | The dubbing timeline has exactly the duration of the video. |
| 100% | `completed` | FFmpeg merges the original video with the new audio and publishes the result. |

Progress is **milestone-based** with an intra-stage percentage. It is not a time
estimate, so the number can stay still for a while during a long stage. Stage
changes always update the progress; intermediate updates are throttled to one
every few seconds so Redis is not flooded.

## Demo: English short to Indonesian dub

> **Disclaimer**
>
> - No sample video is included in this repository. Use only a clip that you own
>   or have permission to process.
> - Machine translation and synthetic speech are not perfect. Always review the
>   result before publishing it.
> - The original audio is replaced, including background music and sound effects.
>   There is no lip-sync, no voice cloning, and no speaker separation.
> - Do not use MyDubber to dub content you are not allowed to copy or modify.

A good first test is a short English clip:

1. Prepare a **10 to 30 second** MP4 with H.264 video and AAC audio. Make sure
   somebody is actually speaking.
2. Upload it (see [step 7](#7-dub-your-first-video)).
3. Watch the stages: `extracted` → `transcribed` → `translated` → `synthesized` → `completed`.
4. Open `download_url`. You now have the same video with Indonesian speech.

Processing time depends on CPU performance, speech density, model loading, and
video length. CPU translation can take longer than the other stages; no fixed
turnaround time is guaranteed.

## Long videos

Two-hour recordings are supported on CPU. Keep these points in mind:

- The default duration limit is **6 hours** (`MYDUBBER_MAX_MEDIA_HOURS`). A
  longer file fails early with a clear message.
- The default upload limit is **4096 MiB**. Raise `MYDUBBER_MAX_UPLOAD_MB` in
  `.env` for larger files; the API and the worker must use the same value.
- Expect roughly **1–1.5 hours** of processing for a 2-hour 1080p video on a
  4-thread CPU with the base Whisper model. This is an estimate, not a promise.
- Free disk space on the storage drive should be at least **twice the video
  size plus 0.35 GB per video hour** for the temporary timeline. The upload is
  first spooled into the system temporary directory, so that drive needs free
  space too.
- The worker must keep running for the whole task. A 2-hour job is not atomic:
  if the worker stops, the upload and the JSON checkpoints are kept for
  `MYDUBBER_RESULT_EXPIRES` seconds (24 hours by default).
- After a failure, requeue the **same task ID** instead of uploading again.
  Finished transcription and translation batches are reused, and synthesis
  restarts from the last completed timeline state.

Requeue a failed task from the project folder while Redis and the worker are
running:

```bash
python -c "from app.tasks import dub_video; dub_video.apply_async(args=['<task_id>'], task_id='<task_id>', retry=False)"
```

The API status for that task will move from `FAILURE` back to `PROGRESS`. Old
uploads and checkpoints that are never retried are deleted automatically after
`MYDUBBER_RESULT_EXPIRES` seconds.

## Quick start

What you need: Docker Desktop, Ollama with the `llama3.2` model, Python 3.10+,
and FFmpeg (installed automatically on Windows). GNU Make is optional and enables
the fast commands below. 16 GB RAM and about 3 GB of disk space are recommended.

Steps 1–3 are one-time setup. Steps 4–7 repeat every time you use MyDubber.

### Fast path with Make

If GNU Make is installed, two commands replace steps 1–6:

```bash
make setup   # once: create .venv, install dependencies, copy .env, download assets
make up      # start Redis, the API, and the worker
```

Docker Desktop must be running. Ollama is never started or stopped by these
targets, so the external host instance is used directly. `make up` prints the
Swagger URL and writes the API and worker logs to `storage/logs/`.

| Command | What it does |
| --- | --- |
| `make setup` | Create `.venv`, install dependencies, copy `.env.example`, download models and tools. |
| `make up` | Start Redis, the API, and the worker in the background. |
| `make stop` | Stop the API and worker; keep Redis running. |
| `make down` | Stop the API, the worker, and Redis. The Redis volume and results are kept. |
| `make status` | Show process, API, Redis, and Ollama status. |
| `make doctor` | Check prerequisites, local assets, ports, and Ollama. |
| `make logs` | Follow the API and worker logs; `make logs-api` or `make logs-worker` for one. |
| `make test` / `make lint` | Run the unit tests or the style checks. |
| `make e2e VIDEO=/path/to/video.mp4` | Run the integration test with a real video. |

Use `make up PORT=8001` if port 8000 is busy, and `make logs LINES=200` to show
more history. Stopping the stack while a dub is running interrupts that task;
the upload and JSON checkpoints are kept for a requeue.

The manual steps below do the same thing without Make.

### 1. Install Docker

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), open
it, and wait until it is running. Docker is used only for Redis.

```bash
docker --version
docker compose version
```

### 2. Install Ollama and the model

Install [Ollama](https://ollama.com/download), then pull the translation model:

```bash
ollama --version
ollama pull llama3.2      # about 2 GB, once only
ollama list               # llama3.2 must be listed
```

The Ollama app must stay running while you use MyDubber. On Windows just open the
desktop app; if you use the CLI, run `ollama serve` in its own terminal.

### 3. Set up the project

```powershell
# Windows PowerShell
git clone <your-repository-url> MyDubber
cd MyDubber
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.prepare_local --download --skip-services
```

```bash
# Linux
git clone <your-repository-url> MyDubber
cd MyDubber
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
sudo apt-get install ffmpeg
python -m scripts.prepare_local --download --skip-services
```

The last script downloads the Whisper model, the Piper voice, and the Swagger UI
assets. On Windows it also installs portable FFmpeg under `tools/ffmpeg/bin`. A
correct run prints `All local assets ready.` and exits without an error.
`--skip-services` checks local assets without requiring Redis or Ollama to be
running yet.

**Do not continue if the download fails or is interrupted.** Fix the reported
error and rerun the same download command; existing files are skipped. Models
are downloaded before Swagger assets, so an interrupted setup can leave
`tools/swagger` missing. The API can still start, but `/docs` will be blank
because its local JavaScript and CSS are unavailable. Keep `tools/` after setup;
these assets are not included in Git and are not downloaded by the API.

### 4. Start Redis

Terminal 1, from the project folder:

```bash
docker compose up -d
docker compose ps      # STATUS must be healthy
```

Redis listens on `127.0.0.1:6379` only. Its data lives in the
`mydubber_redis_data` volume, so the queue survives a container stop.

### 5. Start the worker

Terminal 2, from the project folder. This terminal runs the dubbing pipeline and
prints progress for every video.

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe -m celery -A app.celery_utils:celery_app worker --loglevel=info --pool=solo --concurrency=1
```

```bash
# Linux
source .venv/bin/activate
python -m celery -A app.celery_utils:celery_app worker --loglevel=info --pool=prefork --concurrency=1
```

Ready when it prints `celery@<machine-name> ready.` Keep this terminal open.

### 6. Start the API and Swagger

Terminal 3, from the project folder. First verify the local assets:

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe -m scripts.prepare_local --skip-services
```

```bash
# Linux (virtual environment active)
python -m scripts.prepare_local --skip-services
```

Continue only if this prints `All local assets ready.` and exits without an
error. If assets are missing, rerun the download command in step 3. Then start
the API:

```powershell
# Windows PowerShell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
# Linux
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Ready when it prints `Uvicorn running on http://127.0.0.1:8000`. Open
**http://127.0.0.1:8000/** for the dashboard, or
**http://127.0.0.1:8000/docs** for Swagger UI.

> Port already in use? Change `--port 8000` to `--port 8001`, then open
> `http://127.0.0.1:8001/docs`.

Swagger should show **POST /api/v1/dubbing/tasks** and
**GET /api/v1/dubbing/tasks/{task_id}**. If the page is blank, check
`http://127.0.0.1:8000/docs-assets/swagger-ui-bundle.js` and
`http://127.0.0.1:8000/docs-assets/swagger-ui.css`; both must return HTTP `200`.
An HTTP `404` or `500` means the assets are not being served correctly. Check
the API log and rerun step 3 if files are missing, then press **Ctrl+F5** on
`/docs`. A successful `/openapi.json` response alone does not mean Swagger's
JavaScript and CSS are ready. Use your API port in these URLs if you changed it.

### 7. Dub your first video

The dashboard at **http://127.0.0.1:8000/** is the easiest route: drag an MP4 onto
the drop zone and watch each stage update live. The Swagger flow below is the
equivalent API-only path.

1. Open **http://127.0.0.1:8000/docs**.
2. Open **POST /api/v1/dubbing/tasks** → **Try it out** → choose an MP4 →
   **Execute**. A `202` response means the job is queued, not finished.
3. Copy the `task_id`, then open **GET /api/v1/dubbing/tasks/{task_id}** →
   **Try it out** → paste the `task_id` → **Execute** every 5–10 seconds.
4. When `status` becomes `SUCCESS`, open `download_url` to play or download the
   result.

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

### The same flow with curl

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dubbing/tasks -F "file=@/path/to/video.mp4"
curl http://127.0.0.1:8000/api/v1/dubbing/tasks/<task_id>
```

On Windows PowerShell, use `curl.exe` instead of `curl`.

### Status meanings

| Status | Meaning |
| --- | --- |
| `PENDING` | An uploaded task is waiting for a worker. Unknown or expired IDs without local task files return HTTP `404`; use the `status_url` from your actual upload response, not an example ID. |
| `STARTED` | A worker has picked up the job. |
| `PROGRESS` | Running; see `progress` and `stage`. |
| `SUCCESS` | Done; `download_url` is available. |
| `FAILURE` / `REVOKED` | Failed or cancelled; check the worker log. |

Progress is milestone-based (10 extract, 10–29 transcribe, 30–59 translate, 60–79
synthesize, 80 merge), not a time estimate.

### Upload errors

| Code | Meaning |
| --- | --- |
| `400` | The file is empty. |
| `413` | Over the upload limit (4096 MiB by default). |
| `415` | The extension is not `.mp4`. |
| `422` | Invalid request, or the `task_id` is not a UUID. |
| `503` | Redis is not reachable. |

## Web dashboard

The dashboard is served by the same FastAPI process at
**http://127.0.0.1:8000/** (or `make open`). It is plain HTML, CSS, and
JavaScript with no build step and no CDN, so it works offline like the rest of
the app.

- Drag one or more MP4 files onto the drop zone. Uploads are sent one at a time
  and each file shows its own upload progress.
- Queued and running tasks update live through Server-Sent Events. The list is
  restored from disk when the page or the API restarts.
- Filter by active, completed, or failed tasks, and search by filename.
- Completed tasks can be played in a dialog or downloaded without leaving the
  page.
- The interface is bilingual. It follows the browser language (`id` becomes
  Indonesian, anything else English) and remembers your language and light or
  dark theme in `localStorage`.

The dashboard uses these endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/dubbing/config` | Upload size and duration limits shown in the UI. |
| `GET /api/v1/dubbing/tasks?limit=50` | Persisted task metadata, active first. |
| `GET /api/v1/dubbing/events` | SSE stream of task snapshots (`tasks`) and 15-second heartbeats (`ping`). Hidden from OpenAPI. |
| `POST /api/v1/dubbing/tasks` | Upload and queue a task. |
| `GET /api/v1/dubbing/tasks/{task_id}` | Poll one task. |
| `GET /outputs/{task_id}.mp4` | Play or download a result. |

Task metadata lives in `storage/tasks/<task_id>.json`, written atomically by both
the API and the worker. Up to 200 records are kept, and records without a result
are pruned after `MYDUBBER_RESULT_EXPIRES`. Result videos stay in
`storage/outputs/`.

## Stopping

Stop in the order **API → worker → Redis** so nothing keeps running in the
background.

**1. Stop the API and the worker.** Click each terminal, press `Ctrl+C`, and wait
for the prompt to return. If a terminal was closed with the X button, the process
may still be alive; force-stop it with:

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

**2. Stop Redis.**

```bash
docker compose stop      # container stops, queue data is kept
```

**3. Confirm nothing is left.**

```bash
docker compose ps        # no service may be Up
Get-Process python       # no worker/API process may remain
ollama ps                # the model unloads automatically after 5 idle minutes
```

**4. Optional.** Remove the container with `docker compose down` (data kept) or
`docker compose down -v` (queue data deleted). To free memory immediately, run
`ollama stop llama3.2`. To shut Docker down completely, run `docker desktop stop`.

To run again: `docker compose start`, then repeat steps 5 and 6.

## Plain-English glossary

| Word | Simple meaning |
| --- | --- |
| **API** | A way for programs to talk to each other over HTTP. |
| **Endpoint** | One URL that does one job, such as `/api/v1/dubbing/tasks`. |
| **Request / response** | What you send, and what the server sends back. |
| **JSON** | The text format used for responses, like `{"status": "SUCCESS"}`. |
| **Task** | One dubbing job, identified by a `task_id` (a UUID). |
| **Queue** | A waiting line for jobs. Redis holds this line. |
| **Worker** | The background program that takes jobs from the queue and does the work. |
| **Poll** | To ask the server "is it done yet?" again and again. |
| **Container** | A small, isolated environment that runs one service. |
| **Image** | The saved template used to start a container. |
| **Volume** | Storage that survives when a container is removed. |
| **Port** | A number that identifies a service on a machine, such as `8000`. |
| **Swagger UI** | The web page at `/docs` where you can try the API by clicking. |

## Configuration

Copy `.env.example` to `.env`. All application settings use the `MYDUBBER_`
prefix. The API and the worker must use the same configuration and the same
storage directory.

`.env` is read by the API and the worker running natively. `docker-compose.yml`
holds Redis only and does not use application variables; change the Redis port
there if 6379 is already taken.

The table below covers every application setting:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYDUBBER_STORAGE_DIR` | `./storage` | Where uploads, temporary files, and results are stored. |
| `MYDUBBER_REDIS_URL` | `redis://127.0.0.1:6379/0` | Celery broker. |
| `MYDUBBER_REDIS_RESULT_URL` | `redis://127.0.0.1:6379/1` | Celery result backend. |
| `MYDUBBER_OLLAMA_URL` | `http://127.0.0.1:11434/api/generate` | Ollama generation endpoint. |
| `MYDUBBER_OLLAMA_MODEL` | `llama3.2` | Translation model. |
| `MYDUBBER_WHISPER_MODEL_DIR` | `./models/whisper-base` | Local Whisper model directory. |
| `MYDUBBER_PIPER_MODEL_PATH` | `./models/piper/id_ID-news_tts-medium.onnx` | Local Piper voice. |
| `MYDUBBER_CPU_THREADS` | `4` | Thread setting used by FFmpeg, Whisper, and Ollama. Range 1–16; does not configure Piper's ONNX session. |
| `MYDUBBER_MAX_UPLOAD_MB` | `4096` | Upload limit in MiB. |
| `MYDUBBER_MAX_MEDIA_HOURS` | `6` | Maximum accepted video duration, in hours. |
| `MYDUBBER_RESULT_EXPIRES` | `86400` | How long task metadata stays in Redis, and how long failed uploads/checkpoints are kept, in seconds. |
| `MYDUBBER_OLLAMA_TIMEOUT` | `300` | Timeout per translation request, in seconds. |
| `MYDUBBER_FFMPEG_TIMEOUT` | `7200` | Timeout per FFmpeg/FFprobe call, in seconds. |
| `MYDUBBER_TRANSLATION_BATCH_CHARS` | `700` | Maximum transcript characters per Ollama request. Set `0` to translate one segment per request. |
| `MYDUBBER_TRANSLATION_BATCH_SEGMENTS` | `8` | Maximum segments per Ollama request. |
| `MYDUBBER_TRANSLATION_RETRIES` | `3` | Attempts per translation request before the task fails. |
| `MYDUBBER_PROGRESS_MIN_INTERVAL` | `5` | Minimum seconds between intra-stage progress updates. |
| `MYDUBBER_TASK_VISIBILITY_TIMEOUT` | `43200` | Redis broker visibility timeout. Must exceed the longest task. |
| `MYDUBBER_FFMPEG_BINARY` | auto | Override the FFmpeg executable path. |
| `MYDUBBER_FFPROBE_BINARY` | auto | Override the FFprobe executable path. |
| `MYDUBBER_CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Allowed browser origins, as a JSON array. |

Relative paths are resolved from the current working directory. The API and
worker block connections to non-loopback hosts, so Redis and Ollama must run on
`localhost`.

## Models, voices, and assets

| Component | What MyDubber uses | Source and terms |
| --- | --- | --- |
| Speech recognition | faster-whisper `base`, CPU, INT8 | [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base) |
| Translation | `llama3.2` through Ollama, temperature 0, GPU disabled | [Ollama library](https://ollama.com/library/llama3.2) — Meta Llama 3.2 terms |
| Indonesian voice | `id_ID-news_tts-medium` | [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/id/id_ID/news_tts/medium) |
| Media | FFmpeg and FFprobe | Windows build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), or your OS package |
| API docs | Swagger UI 5.17.14, stored locally | [swagger-ui-dist](https://www.npmjs.com/package/swagger-ui-dist) — Apache-2.0 |

### About the Indonesian voice

| Property | Value |
| --- | --- |
| Voice ID | `id_ID-news_tts-medium` |
| Language | Indonesian (`id_ID`), one speaker |
| Quality | medium, 22,050 Hz (used natively for the dubbing timeline) |
| Phonemizer | eSpeak NG, voice `id`, running locally |
| Training data | `news_tts`. The model card links the dataset and says "License: See URL". |
| Repository license | The Piper voices repository declares MIT. The dataset terms may differ. |

The voice files are downloaded once by `scripts/prepare_local.py` and then loaded
from disk. Nothing is downloaded at runtime.

## Testing

### Unit tests (no services needed)

Unit tests mock Redis, Ollama, Whisper, Piper, and media processing. You can run
them on any machine, without models or containers.

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
python -m pip check
```

The checks are supported on Windows and Linux with Python 3.10 and 3.12.

### Integration test with a real video

This test uploads a real file through the API and checks the whole pipeline. It
needs Redis, Ollama, the worker, the API, and all local assets.

```bash
python -m scripts.test_local /path/to/sample-en.mp4
```

Use a short English clip that you own. The test checks:

- Swagger UI and its local assets load,
- the upload is accepted with HTTP 202,
- the task reaches `SUCCESS` with `progress: 100`,
- the output duration matches the source within 0.25 seconds,
- the video bitstream is unchanged (the picture was not re-encoded),
- the audio is not silent,
- the downloaded bytes match the rendered file,
- HTTP Range requests return `206`,
- temporary upload and work files are deleted.

The wait timeout is scaled from the video duration by default. Pass `--timeout`
to override it. The report is saved to `storage/e2e-report.json`.

## Offline use

After the one-time installation, MyDubber works without internet:

- Whisper loads a local model and never falls back to downloading.
- Piper loads its voice and phonemizer from disk. There is no online TTS fallback.
- Redis and Ollama URLs must point to loopback addresses.
- The API and worker block non-loopback socket connections and disable Hugging
  Face downloads and telemetry.
- FFmpeg accepts only local `file` and `pipe` protocols.
- Swagger assets are served locally. The external validator is disabled.
- The Redis container uses an image that is already on the machine; `docker compose`
  does not pull it again on restart.

The Python checks are application-level restrictions, not a system firewall. For a
machine without internet, transfer Python packages, Whisper/Piper model files,
FFmpeg, and the Redis image (`docker save`/`docker load`) using local media. Ollama
and the `llama3.2` model must also be installed before the machine goes offline.

## Cleaning generated data

No input videos, dubbed examples, integration reports, or runtime caches are
shipped with the source. Normal use still uploads videos through the API.

Stop the API and worker and close video players before deleting files. Queue data
and task metadata live in the `mydubber_redis_data` Redis volume. To remove them
as well, run:

```bash
docker compose down --volumes
```

This is destructive and cannot be undone.

For a **native** installation using the default storage path, stop the API and
worker, then remove `storage/` from the repository root:

```powershell
if (Test-Path storage) { Remove-Item -LiteralPath storage -Recurse -Force }
```

On Linux/macOS, the equivalent is `rm -rf -- storage`. If you configured another
storage location, clean that location instead. Native Redis metadata is separate.
The API recreates its upload, temp, and output directories at the next startup.

Keep `models/` and `tools/` for offline operation. `.venv/` is only needed for a
native installation or development. The `llama3.2` model is managed by Ollama in
its own model directory, outside this repository.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Swagger `/docs` is blank | Local Swagger JavaScript/CSS are missing, often after an interrupted setup. | Rerun the download command in [step 3](#3-set-up-the-project), wait for `All local assets ready.` without errors, check `/docs-assets/swagger-ui-bundle.js` and `/docs-assets/swagger-ui.css` return `200`, then press Ctrl+F5. |
| Task stays `PENDING` forever | Worker is not running, or it uses a different Redis. | Start the worker. Check that both processes use the same `MYDUBBER_REDIS_URL`. |
| Upload returns `503` | Redis is not reachable. | Start Redis, then check `docker compose ps`. |
| Polling returns `503` | The result backend is not reachable. | Check `MYDUBBER_REDIS_RESULT_URL`. |
| Task ends in `FAILURE` with "model is not available" | Model files are missing. | Run `python -m scripts.prepare_local --download`. |
| Task ends in `FAILURE` with "Program not found" | FFmpeg is not installed or not on `PATH`. | Install FFmpeg, or set `MYDUBBER_FFMPEG_BINARY`. |
| "No speech was detected" | The video has music but no voice, or the speech is too quiet. | Use a clip with clear speech. |
| Upload returns `415` | The file is not named `.mp4`. | Rename or remux the file to MP4 first. |
| Port 8000 is already in use | Another program uses the port. | Start uvicorn with `--port 8001`. |
| Port 6379 is already in use | Another Redis is already running. | Stop it, or change the port in `docker-compose.yml` and both Redis URLs. |
| `prepare_local` fails at the Ollama check | Ollama is not running, or `llama3.2` is not pulled. | Run `ollama serve`, then `ollama pull llama3.2`. |
| Celery fails on Windows | The default pool is not supported. | Use `--pool=solo` as shown above. |
| First run is very slow | Models are being loaded for the first time. | Wait. Later runs reuse the loaded models. |
| Output does not play in some players | `-c:v copy` kept a codec the player does not support. | Use a standard H.264/AAC MP4. |
| `make: command not found` | GNU Make is not installed. | Follow the manual steps in [Quick start](#quick-start), or install Make (for example `choco install make`). |
| `make up` says Docker is not ready | Docker Desktop is stopped or still starting. | Open Docker Desktop, wait until it is running, then run `make up` again. |
| `make up` says port 8000 is in use | Another API or program owns the port. | Stop it, or run `make up PORT=8001` and open the new URL. |
| `make up` warns that Ollama is not reachable | The external Ollama service is not running. | Start the Ollama app or run `ollama serve`; pull the model with `ollama pull llama3.2`. |
| `make stop` leaves a process | It was started manually, outside the Makefile. | Stop it in its original terminal, or use Task Manager / `taskkill`. |
| A long task stays at 30% for a long time | Translation of a large transcript is CPU-heavy. | Wait, or lower `MYDUBBER_CPU_THREADS` contention by closing other programs. Check the worker log for per-batch warnings. |
| A long task fails after a worker restart | The job was interrupted, not cancelled. | Restart Redis and the worker, then requeue the same task ID as described in [Long videos](#long-videos). |
| A long video returns `413` | The file is above `MYDUBBER_MAX_UPLOAD_MB`. | Raise it in `.env` for both the API and the worker. |
| "Not enough free disk space" | The storage drive cannot hold the upload plus the temporary timeline. | Free space, raise `MYDUBBER_STORAGE_DIR` to another drive, or shorten the video. |
| "configured limit is 6.0 hours" | The duration guard rejected the video. | Raise `MYDUBBER_MAX_MEDIA_HOURS` if the machine can handle it. |

## Limitations and security

- **Trusted local use only.** There is no authentication, rate limiting, or
  storage quota. Only a configurable duration limit (`MYDUBBER_MAX_MEDIA_HOURS`)
  guards resource use. Do not expose the API, Redis, or Ollama to the internet.
- CORS is not access control.
- The upload size is checked as early as possible, but FastAPI still spools the
  multipart body to the system temporary directory before the API reads it. Add a
  request-body limit at your proxy if you put one in front of the API.
- The original audio is replaced, including background music. There is no voice
  cloning, speaker diarization, background separation, or lip-sync.
- Speech may be sped up or padded to fit the original timestamps. Translation and
  technical terms need human review.
- Incompatible MP4 codecs can make the video merge fail.
- Successful tasks delete their upload and temporary files. Failed tasks keep the
  upload and JSON checkpoints until `MYDUBBER_RESULT_EXPIRES` elapses, so they can
  be requeued. A forced worker kill can leave files or tasks in `STARTED`.
- Results stay on disk until you delete them. Task metadata expires after 24 hours
  by default, but the video files do not.
- Tasks are not retried automatically. Requeue the same task ID after checking the
  worker log; completed checkpoints are reused.
- Keep concurrency at 1 on machines with limited memory. Whisper and Piper are
  cached per worker process, and Ollama keeps the model loaded for five minutes.

## Project layout

```text
app/
  main.py           FastAPI app, dashboard, upload, list, and status endpoints
  config.py         Settings with the MYDUBBER_ prefix
  celery_utils.py   Celery broker and result backend
  offline.py        Loopback-only network policy
  tasks.py          The dubbing pipeline, checkpoints, and progress reporting
  task_store.py     Atomic JSON task registry shared by the API and the worker
  events.py         Server-Sent Events broker for live dashboard updates
  web/
    index.html      Dashboard markup
    styles.css      Dark and light studio theme
    app.js          Upload queue, SSE client, i18n, and player logic
scripts/
  dev.py            Start, stop, status, and log helpers used by the Makefile
  prepare_local.py  One-time asset download and local verification
  test_local.py     Real-media integration test
tests/
  test_backend.py   Unit and API contract tests
  test_task_store.py  Task registry and pruning tests
  test_events.py    SSE formatting and broker tests
  test_dev_script.py  Tests for the developer helper
docs/
  logo.svg          Project logo
Makefile            One-command start and stop for Redis, API, and worker
docker-compose.yml  One service: Redis for the task queue and result metadata
```

`models/` and `tools/` are local assets excluded from version control. `storage/`
is generated at runtime and is also ignored. The `llama3.2` model is stored by
Ollama in its own model directory, outside this repository. No `video/` directory
is required. Do not publish private media, generated reports, or model weights
with the source code.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, checks, and
pull request rules. In short: keep it CPU-only, keep it offline after install,
and do not add runtime downloads or cloud fallbacks.

## License

MyDubber is released under the **MyDubber License**: you may use, modify, and
redistribute it, including commercially, as long as you keep the copyright
notice and give clear credit to **MyDubber contributors**. See [LICENSE](LICENSE).

This license covers the source code in this repository only. Third-party
software and pretrained assets keep their own terms. In particular, review:

- Piper's GPL-3.0 license and the Piper voice model card and dataset terms,
- the Llama 3.2 model terms,
- your Redis version's license,
- the license of your FFmpeg build (LGPL or GPL depending on the build),
- the Apache-2.0 license of Swagger UI.

Installing a dependency does not make its assets part of the MyDubber license.
