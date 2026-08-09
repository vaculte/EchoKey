# --- Builder stage ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /build/
COPY app /build/app

RUN pip wheel --no-cache-dir -w /wheels /build

# --- Runtime stage ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels echokey-backend && \
    rm -rf /wheels

RUN useradd -u 1000 appuser && mkdir -p /app/uploads && chown -R appuser /app
USER appuser

EXPOSE 8000