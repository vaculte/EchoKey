# EchoKey

[English](README.md) · [Русский](README.ru.md) · [Українська](README.uk.md)

> Локальний voice-to-text помічник для Linux із пріоритетом приватності.

EchoKey перетворює диктування за утримання hotkey на текст в активному полі
введення. Аудіо обробляється локальною моделлю Vosk і не надсилається до
сторонніх сервісів розпізнавання мовлення.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux-FCC624?logo=linux&logoColor=black)
![Docker](https://img.shields.io/badge/Runtime-Docker-2496ED?logo=docker&logoColor=white)
![Speech recognition](https://img.shields.io/badge/Speech%20recognition-Vosk-6B4FBB)

## Чому EchoKey

- **Offline за замовчуванням** — транскрибування працює на локальній моделі
  Vosk.
- **Нативний Linux-сценарій** — утримуйте global hotkey для запису та
  відпускайте його, щоб вставити транскрипцію в активну програму.
- **Підтримка Wayland і X11** — використовуються `evdev`/`wtype` у Wayland та
  fallback-механізми `pynput` у X11.
- **Backend, готовий до розгортання** — FastAPI, PostgreSQL, Redis і Celery
  worker працюють через Docker Compose або перевірений локальний Kubernetes lab.

## Архітектура

```text
Linux desktop client
  ├── записує 16 kHz WAV audio
  ├── завантажує його до FastAPI
  └── вставляє готову транскрипцію в активне поле

FastAPI ──► PostgreSQL              зберігає метадані записів і транскрипції
     │
     └──► Redis ──► Celery worker ──► локальна модель Vosk
                                      транскрибує збережений WAV file
```

API і worker використовують один backend image та відрізняються лише командою
запуску. Завантажене аудіо зберігається локально у налаштованому uploads volume.

## Технології

| Напрям | Технології |
| --- | --- |
| Desktop client | Python, `sounddevice`, `pynput`, `evdev`, `wtype` |
| API | FastAPI, Pydantic, SQLAlchemy async |
| Фонові задачі | Celery, Redis |
| Дані | PostgreSQL 15 |
| Розпізнавання мовлення | Vosk |
| Delivery і quality | Docker Compose, Kubernetes, kind, Calico, Traefik, GitHub Actions, Ruff, pytest, unittest |

## Швидкий старт

### 1. Підготуйте локальну Vosk model

Завантажте сумісну модель із [каталогу Vosk](https://alphacephei.com/vosk/models/)
та розпакуйте її вміст до `models/vosk/`.

У директорії мають з'явитися папки моделі, наприклад `am/`, `conf/`, `graph/`
і `ivector/`. Моделі навмисно не зберігаються в Git і не включаються до Docker
image.

### 2. Запустіть backend stack

```bash
cp .env.example .env
docker compose up --build
```

Команда запустить PostgreSQL, Redis, FastAPI API та Celery worker. Перевірте
стан stack:

```bash
curl http://localhost:8000/health
```

### 3. Встановіть і запустіть desktop client

У другому терміналі:

```bash
cd client
python -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -e .
echokey
```

Default hotkey — **F4**: утримуйте його для запису та відпускайте для
транскрибування. API endpoint і hotkey налаштовуються у `client/.env`:

```env
ECHOKEY_API_URL=http://localhost:8000
HOTKEY=<ctrl>+<shift>+r
DEBUG=false
```

Відстежуваний client example налаштований на перевірений Kubernetes HTTPS
endpoint. Для Docker Compose задайте
`ECHOKEY_API_URL=http://localhost:8000` в ігнорованому `client/.env`, як
показано вище.

`cmd`, `super` і `win` — еквівалентні aliases одного modifier.

## Локальне Kubernetes-розгортання

Kubernetes lab версії v0.1 перевірено end to end: нативний Wayland client
завантажує запис через Traefik Ingress із довіреним локальним HTTPS, API
зберігає WAV у спільному NFS-backed PVC, Celery отримує Redis-задачу на іншій
worker node, Vosk розпізнає мовлення, а клієнт вставляє збережений результат.

Розгортання використовує тривузловий kind cluster із Calico, постійними
томами PostgreSQL і Redis, відновлюваним PVC моделі Vosk та незмінним GHCR
image. Топологію, prerequisites, порядок встановлення, налаштування TLS,
перевірки та межі відновлення описано в
[`k8s/README.md`](k8s/README.md).

## Вимоги Linux desktop

| Session | Hotkey і введення тексту |
| --- | --- |
| X11 | `pynput` та fallback через clipboard paste |
| Wayland | `evdev` для global keys; `wl-copy` і `wtype` для вставки тексту |

Для Wayland встановіть `wtype` і `wl-clipboard`, потім надайте поточному
користувачу доступ до input devices:

```bash
# Arch / Manjaro
sudo pacman -S wtype wl-clipboard
sudo usermod -aG input "$USER"
```

Після зміни групи вийдіть із сесії та увійдіть знову. Якщо `evdev`
недоступний, EchoKey використає `pynput`; він найнадійніший у XWayland windows.

## API та observability

| Endpoint | Призначення |
| --- | --- |
| `GET /health` | Незалежна від залежностей перевірка процесу |
| `GET /ready` | Готовність PostgreSQL і Redis |
| `GET /metrics` | Prometheus metrics |
| `POST /recordings` | Завантажує WAV recording і ставить транскрибування в чергу |
| `GET /recordings/{id}` | Повертає status і результат транскрибування |

## Development checks

Backend checks потребують PostgreSQL; Redis і Celery замокані у test suite:

```bash
cd backend
ruff check .
pytest
```

Client checks — headless unit tests; їм не потрібні мікрофон, display server чи
backend services:

```bash
cd client
ruff check .
python -m unittest discover tests
```

GitHub Actions запускає відповідні lint і test workflows для змін backend і
client у pull request.

## Структура проєкту

```text
backend/    FastAPI API, Celery worker, database migrations і pytest suite
client/     Linux desktop client і unit tests
models/     mount point для локальної Vosk model (не комітиться)
.github/    pull-request quality checks
k8s/        перевірене ручне локальне Kubernetes-розгортання
```

## Roadmap

- [x] Dockerized local stack
- [x] Pull-request lint і test checks для backend і client
- [x] Публікація container images після merge у `main`
- [x] Перевірене локальне Kubernetes-розгортання та HTTPS client flow
- [ ] Prometheus і Grafana dashboard

Наступні Kubernetes-етапи: Helm packaging, встановлення кількох environments,
NetworkPolicies, recovery checks і automation.

---

EchoKey створено як local-first проєкт: аудіо залишається на машині, де ви його
запускаєте.
