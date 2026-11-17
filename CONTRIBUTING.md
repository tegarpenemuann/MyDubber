# Contributing

MyDubber is a local-first, CPU-only video dubbing backend, released under the
[MyDubber License](LICENSE) (attribution required). Changes should preserve
offline operation after installation and the existing asynchronous upload API.

All code, comments, and user-facing messages in this repository are written in
English, except for the bilingual dashboard strings in `app/web/app.js`. User
documentation is available in English ([README.md](README.md)) and Indonesian
([README.id.md](README.id.md)).

## Development Setup

Use Python 3.10 or later and create a virtual environment as described in the
[README](README.md). Install development dependencies instead of the runtime-only
requirements:

```bash
python -m pip install -r requirements-dev.txt
```

With GNU Make installed, `make setup` performs the same installation and asset
download, while `make up` and `make down` manage Redis, the API, and the worker.
Ollama remains external and is never started or stopped by the Makefile.

The commands below assume the virtual environment is active. On Windows, you can
use `.venv\Scripts\python.exe` instead of `python` without activating it.

## Checks

```bash
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
python -m pip check
```

Apply formatting with `python -m ruff format .`. Unit tests mock Redis, Ollama,
Whisper, Piper, and media processing; they do not need running services or model
downloads. The project targets Python 3.10 and 3.12.

With GNU Make installed, `make test` and `make lint` run the same checks. Use
`make up` / `make stop` / `make down` for the local stack.

For changes to the dubbing pipeline, run the real integration check using a video
you have permission to process:

```bash
python -m scripts.test_local /path/to/sample.mp4
```

This requires local assets, Redis, Ollama, the worker, and the API. It uploads via
HTTP and verifies media integrity, audio, downloads, streaming, and cleanup.
Integration reports and generated media remain local under `storage/`.

## Pull Requests

- Keep changes focused and add regression tests for changed behavior.
- Preserve CPU operation, local model loading, and loopback-only service URLs.
- Do not add runtime downloads, cloud fallbacks, analytics, or external Swagger assets.
- Keep API examples, configuration, and setup instructions in sync with code.
- Do not commit `.env` files, virtual environments, models, executables, private
  media, generated outputs, or logs. Do not copy third-party assets into source.
- Describe the problem, the change, and the checks you ran. Mention any limitations.

## Reporting Problems

Include your operating system, Python version, installation steps, relevant task
state, and a minimal reproduction. Redact personal paths, transcripts, credentials,
and private video content from logs. Do not post sensitive material in public issues.

## Licensing

MyDubber is released under the [MyDubber License](LICENSE): free to use, modify,
and redistribute, with attribution to "MyDubber contributors". Third-party
software and models keep their own licenses. Do not assume the MyDubber license
covers bundled dependencies or pretrained weights.