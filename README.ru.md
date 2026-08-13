# EchoKey

[English](README.md) · [Русский](README.ru.md) · [Українська](README.uk.md)

> Локальный voice-to-text помощник для Linux с приоритетом приватности.

EchoKey превращает диктовку по удержанию hotkey в текст в активном поле ввода.
Аудио обрабатывается локальной моделью Vosk и не отправляется в сторонние
сервисы распознавания речи.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux-FCC624?logo=linux&logoColor=black)
![Docker](https://img.shields.io/badge/Runtime-Docker-2496ED?logo=docker&logoColor=white)
![Speech recognition](https://img.shields.io/badge/Speech%20recognition-Vosk-6B4FBB)

## Почему EchoKey

- **Offline по умолчанию** — транскрибация работает на локальной модели Vosk.
- **Нативный Linux-сценарий** — удерживайте global hotkey для записи и
  отпускайте, чтобы вставить транскрипцию в активное приложение.
- **Поддержка Wayland и X11** — используются `evdev`/`wtype` в Wayland и
  fallback-механизмы `pynput` в X11.
- **Backend, готовый к развёртыванию** — FastAPI, PostgreSQL, Redis и Celery
  worker доступны в Docker Compose stack.

## Архитектура

```text
Linux desktop client
  ├── записывает 16 kHz WAV audio
  ├── загружает его в FastAPI
  └── вставляет готовую транскрипцию в активное поле

FastAPI ──► PostgreSQL              хранит метаданные записей и транскрипции
     │
     └──► Redis ──► Celery worker ──► локальная модель Vosk
                                      транскрибирует сохранённый WAV file
```

API и worker используют один backend image и отличаются только командой
запуска. Загруженное аудио хранится локально в настроенном uploads volume.

## Технологии

| Область | Технологии |
| --- | --- |
| Desktop client | Python, `sounddevice`, `pynput`, `evdev`, `wtype` |
| API | FastAPI, Pydantic, SQLAlchemy async |
| Фоновые задачи | Celery, Redis |
| Данные | PostgreSQL 15 |
| Распознавание речи | Vosk |
| Delivery и quality | Docker Compose, GitHub Actions, Ruff, pytest, unittest |

## Быстрый старт

### 1. Подготовьте локальную Vosk model

Скачайте совместимую модель из [каталога Vosk](https://alphacephei.com/vosk/models/)
и распакуйте её содержимое в `models/vosk/`.

В директории должны появиться папки модели, например `am/`, `conf/`, `graph/`
и `ivector/`. Модели намеренно не хранятся в Git и не включаются в Docker image.

### 2. Запустите backend stack

```bash
cp .env.example .env
docker compose up --build
```

Команда запустит PostgreSQL, Redis, FastAPI API и Celery worker. Проверьте
здоровье stack:

```bash
curl http://localhost:8000/health
```

### 3. Установите и запустите desktop client

Во втором терминале:

```bash
cd client
python -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -e .
echokey
```

Default hotkey — **F4**: удерживайте его для записи и отпускайте для
транскрибации. API endpoint и hotkey настраиваются в `client/.env`:

```env
ECHOKEY_API_URL=http://localhost:8000
HOTKEY=<ctrl>+<shift>+r
DEBUG=false
```

`cmd`, `super` и `win` — эквивалентные aliases для одного modifier.

## Требования Linux desktop

| Session | Hotkey и ввод текста |
| --- | --- |
| X11 | `pynput` и fallback через clipboard paste |
| Wayland | `evdev` для global keys; `wl-copy` и `wtype` для вставки текста |

Для Wayland установите `wtype` и `wl-clipboard`, затем дайте текущему
пользователю доступ к input devices:

```bash
# Arch / Manjaro
sudo pacman -S wtype wl-clipboard
sudo usermod -aG input "$USER"
```

После изменения группы выйдите из сессии и войдите снова. Если `evdev`
недоступен, EchoKey использует `pynput`; он наиболее надёжен в XWayland windows.

## API и observability

| Endpoint | Назначение |
| --- | --- |
| `GET /health` | Состояние PostgreSQL и Redis |
| `GET /metrics` | Prometheus metrics |
| `POST /recordings` | Загружает WAV recording и ставит транскрибацию в очередь |
| `GET /recordings/{id}` | Возвращает status и результат транскрибации |

## Development checks

Backend checks требуют PostgreSQL; Redis и Celery замоканы в test suite:

```bash
cd backend
ruff check .
pytest
```

Client checks — headless unit tests; им не нужны микрофон, display server или
backend services:

```bash
cd client
ruff check .
python -m unittest discover tests
```

GitHub Actions запускает соответствующие lint и test workflows для изменений
backend и client в pull request.

## Структура проекта

```text
backend/    FastAPI API, Celery worker, database migrations и pytest suite
client/     Linux desktop client и unit tests
models/     mount point для локальной Vosk model (не коммитится)
.github/    pull-request quality checks
```

## Roadmap

- [x] Dockerized local stack
- [x] Pull-request lint и test checks для backend и client
- [ ] Публикация container images после merge в `main`
- [ ] Kubernetes deployment manifests
- [ ] Prometheus и Grafana dashboard

---

EchoKey построен как local-first проект: аудио остаётся на машине, где вы его
запускаете.
