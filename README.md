# EchoKey

Local voice-to-text input for Linux. A minimal global-hotkey dictation assistant that uses a local Vosk backend and types the transcription into the active field.

## Backend local run

Requires PostgreSQL and Redis running locally.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Default environment:

```bash
DATABASE_URL=postgresql+asyncpg://echokey:echokey@localhost:5432/echokey
REDIS_URL=redis://localhost:6379/0
VOSK_MODEL_PATH=./models/vosk-model-small-en-us-0.15
AUDIO_UPLOAD_DIR=./uploads
```

Worker and client will be added in the next layers.
