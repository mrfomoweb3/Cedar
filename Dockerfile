# Cedar — single-service image: FastAPI + in-process autonomous scheduler,
# also serving the built dashboard (one URL, no CORS). Ideal for Railway/Fly.
#
# IMPORTANT: run with a SINGLE worker / one replica. The scheduler is an
# in-process background thread; N workers = N autonomous loops all signing txns.

# --- stage 0: build casper-client (real server-side signing) ---
# CasperKeySigner shells out to this binary to submit reallocate deploys, so it
# must exist in the runtime image. Pinned to 5.0.1 — the version proven against
# the live testnet VaultRouter. Built from source so it links this image's
# libssl3 (Debian bookworm), avoiding the apt-repo libssl1.1 mismatch.
FROM rust:1-slim-bookworm AS casperbin
RUN apt-get update && apt-get install -y --no-install-recommends \
      pkg-config libssl-dev build-essential cmake ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN cargo install casper-client --version 5.0.1 --locked --root /usr/local

# --- stage 1: build the dashboard (same-origin API base) ---
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# empty base => the dashboard calls the same origin that serves it
ENV VITE_API_BASE=""
RUN npm run build

# --- stage 2: python runtime ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CEDAR_DB=/data/cedar.db \
    FRONTEND_DIST=/app/frontend/dist

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# real server-side signer binary (from the casperbin stage)
COPY --from=casperbin /usr/local/bin/casper-client /usr/local/bin/casper-client

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY agent/ agent/
COPY api/ api/
COPY --from=frontend /fe/dist /app/frontend/dist

# /data holds the SQLite fallback DB. We create the dir but deliberately do NOT
# declare a VOLUME: Railway rejects Dockerfiles containing the VOLUME directive.
# For persistence, attach a managed Volume mounted at /data in the platform
# dashboard (or use DATABASE_URL / Postgres, which is preferred in production).
RUN mkdir -p /data

EXPOSE 8000
# Railway/Fly inject $PORT; default to 8000 locally.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/healthz" || exit 1

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
