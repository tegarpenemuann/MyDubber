# MyDubber developer commands.
#
# Redis runs through Docker Compose. The API and worker run natively so they
# can reach the host Ollama instance directly. Ollama is never started or
# stopped by these targets.

ifeq ($(OS),Windows_NT)
FALLBACK_PYTHON := python
else
FALLBACK_PYTHON := python3
endif

PYTHON := $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,$(if $(wildcard .venv/bin/python),.venv/bin/python,$(FALLBACK_PYTHON)))

PORT ?= 8000
VIDEO ?=
LINES ?= 50

.DEFAULT_GOAL := help

.PHONY: help setup up stop down restart status doctor logs logs-api logs-worker test lint e2e open

help:
	@echo "MyDubber commands:"
	@echo "  make setup        Create .venv, install dependencies, copy .env, download assets"
	@echo "  make up           Start Redis, the API, and the worker"
	@echo "  make stop         Stop the API and worker; keep Redis running"
	@echo "  make down         Stop the API, the worker, and Redis (data is kept)"
	@echo "  make restart      Restart the whole stack"
	@echo "  make status       Show process, Redis, API, and Ollama status"
	@echo "  make doctor       Check prerequisites and local assets"
	@echo "  make logs         Follow API and worker logs"
	@echo "  make logs-api     Follow only the API log"
	@echo "  make logs-worker  Follow only the worker log"
	@echo "  make open         Open the dashboard at http://127.0.0.1:$(PORT)/"
	@echo "  make test         Run the unit tests"
	@echo "  make lint         Check and verify formatting"
	@echo "  make e2e VIDEO=...  Run the integration test with a real video"
	@echo ""
	@echo "Options: PORT=$(PORT) LINES=$(LINES)"
	@echo "Ollama must already be running; these targets never manage it."

setup:
	$(PYTHON) -m scripts.dev setup

up:
	$(PYTHON) -m scripts.dev up --port $(PORT)

stop:
	$(PYTHON) -m scripts.dev stop

down:
	$(PYTHON) -m scripts.dev down

restart:
	$(PYTHON) -m scripts.dev restart --port $(PORT)

status:
	$(PYTHON) -m scripts.dev status --port $(PORT)

doctor:
	$(PYTHON) -m scripts.dev doctor --port $(PORT)

logs:
	$(PYTHON) -m scripts.dev logs --lines $(LINES)

logs-api:
	$(PYTHON) -m scripts.dev logs api --lines $(LINES)

logs-worker:
	$(PYTHON) -m scripts.dev logs worker --lines $(LINES)

open:
	@$(PYTHON) -c "import webbrowser; webbrowser.open('http://127.0.0.1:$(PORT)/')"

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

e2e:
ifeq ($(strip $(VIDEO)),)
	@echo "Usage: make e2e VIDEO=/path/to/video.mp4"
	@exit 1
else
	$(PYTHON) -m scripts.test_local "$(VIDEO)"
endif
