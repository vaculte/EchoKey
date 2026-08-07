# EchoKey

Local voice-to-text input for Linux. A minimal global-hotkey dictation assistant that uses a local Vosk backend and types the transcription into the active field.

## Backend local run

Requires PostgreSQL and Redis running locally.

### 1. Download a Vosk model

```bash
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
```

### 2. Install dependencies and run migrations

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -e .
alembic upgrade head
```

### 3. Start API server

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Start Celery worker (in another terminal)

```bash
cd backend
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

### Default environment

```bash
DATABASE_URL=postgresql+asyncpg://echokey:echokey@localhost:5432/echokey
REDIS_URL=redis://localhost:6379/0
VOSK_MODEL_PATH=./models/vosk-model-small-en-us-0.15
AUDIO_UPLOAD_DIR=./uploads
```

## Client local run

Requires a microphone and an X11 session.

```bash
cd client
python -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -e .
echokey
```

Default hotkey: **F12**. Hold to record, release to send and type.

Client environment:

```bash
ECHOKEY_API_URL=http://localhost:8000
HOTKEY=f12
```
