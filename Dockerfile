# ── Build stage ──────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir -U pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV PORT=10000
EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"
