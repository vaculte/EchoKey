# EchoKey

[English](README.md) · [Русский](README.ru.md) · [Українська](README.uk.md)

> A privacy-first, offline voice-to-text assistant for Linux.

EchoKey turns held-hotkey dictation into text in the currently focused input
field. Audio is processed locally with Vosk: it is never sent to a third-party
speech service.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux-FCC624?logo=linux&logoColor=black)
![Docker](https://img.shields.io/badge/Runtime-Docker-2496ED?logo=docker&logoColor=white)
![Speech recognition](https://img.shields.io/badge/Speech%20recognition-Vosk-6B4FBB)

## Why EchoKey

- **Offline by design** — transcription runs on a local Vosk model.
- **Native Linux workflow** — hold a global hotkey to record; release it to
  insert the transcription into the active application.
- **Wayland and X11 support** — uses `evdev`/`wtype` on Wayland and `pynput`
  fallbacks on X11.
- **Production-shaped backend** — FastAPI, PostgreSQL, Redis and a Celery
  worker are provided as a Docker Compose stack.

## Architecture

```text
Linux desktop client
  ├── captures 16 kHz WAV audio
  ├── uploads it to FastAPI
  └── pastes the completed transcript into the focused field

FastAPI ──► PostgreSQL              stores recording metadata and transcripts
     │
     └──► Redis ──► Celery worker ──► Vosk local model
                                      transcribes the saved WAV file
```

The API and worker share one backend image and differ only by their startup
command. Uploaded audio is stored locally in the configured uploads volume.

## Tech stack

| Area | Technologies |
| --- | --- |
| Desktop client | Python, `sounddevice`, `pynput`, `evdev`, `wtype` |
| API | FastAPI, Pydantic, SQLAlchemy async |
| Background jobs | Celery, Redis |
| Data | PostgreSQL 15 |
| Speech recognition | Vosk |
| Delivery and quality | Docker Compose, GitHub Actions, Ruff, pytest, unittest |

## Quick start

### 1. Prepare the local Vosk model

Download a compatible Vosk model from the [Vosk model catalogue](https://alphacephei.com/vosk/models/) and extract its contents into `models/vosk/`.

The directory must contain model folders such as `am/`, `conf/`, `graph/` and
`ivector/`. Models are intentionally not stored in Git or baked into the Docker
image.

### 2. Start the backend stack

```bash
cp .env.example .env
docker compose up --build
```

This starts PostgreSQL, Redis, the FastAPI API and the Celery worker. Confirm
that the stack is healthy:

```bash
curl http://localhost:8000/health
```

### 3. Install and run the desktop client

In a second terminal:

```bash
cd client
python -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -e .
echokey
```

The default hotkey is **F4**: hold it to record and release it to transcribe.
Configure the API endpoint and hotkey in `client/.env`:

```env
ECHOKEY_API_URL=http://localhost:8000
HOTKEY=<ctrl>+<shift>+r
DEBUG=false
```

`cmd`, `super` and `win` are equivalent modifier aliases.

## Linux desktop requirements

| Session | Hotkey and text input |
| --- | --- |
| X11 | `pynput` with clipboard paste fallback |
| Wayland | `evdev` for global keys; `wl-copy` and `wtype` for text insertion |

For Wayland, install `wtype` and `wl-clipboard`, then grant the current user
access to input devices:

```bash
# Arch / Manjaro
sudo pacman -S wtype wl-clipboard
sudo usermod -aG input "$USER"
```

Log out and back in after changing the group. If `evdev` is unavailable,
EchoKey falls back to `pynput`, which is most reliable in XWayland windows.

## API and observability

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Reports PostgreSQL and Redis health |
| `GET /metrics` | Exposes Prometheus metrics |
| `POST /recordings` | Uploads a WAV recording and queues transcription |
| `GET /recordings/{id}` | Retrieves transcription status and result |

## Development checks

Backend checks require PostgreSQL; Redis and Celery are mocked in the test
suite:

```bash
cd backend
ruff check .
pytest
```

Client checks are headless unit tests and do not require a microphone, display
server or backend services:

```bash
cd client
ruff check .
python -m unittest discover tests
```

GitHub Actions runs the matching lint and test workflow for backend and client
changes in pull requests.

## Project structure

```text
backend/    FastAPI API, Celery worker, database migrations and pytest suite
client/     Linux desktop client and unit tests
models/     local Vosk model mount point (not committed)
.github/    pull-request quality checks
```

## Roadmap

- [x] Dockerized local stack
- [x] Pull-request lint and test checks for backend and client
- [ ] Publish container images after merge to `main`
- [ ] Kubernetes deployment manifests
- [ ] Prometheus and Grafana dashboard

---

EchoKey is built as a local-first project: audio remains on the machine where
you run it.
