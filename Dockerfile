FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt /app/requirements-dev.txt
RUN python -m pip install --upgrade pip && python -m pip install -r /app/requirements-dev.txt

COPY rust /app/rust
RUN python -m pip install maturin && (cd /app/rust && maturin develop --release || echo 'Rust engine build failed, using Python fallback engine')

COPY gateway /app/gateway
COPY README.md /app/README.md

EXPOSE 8000
CMD ["sh", "-c", "uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
