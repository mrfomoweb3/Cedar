# Cedar — single-service image: FastAPI + in-process autonomous scheduler,
# also serving the built dashboard (one URL, no CORS). Ideal for Railway/Fly.
#
# IMPORTANT: run with a SINGLE worker / one replica. The scheduler is an
# in-process background thread; N workers = N autonomous loops all signing txns.

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

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY agent/ agent/
COPY api/ api/
COPY --from=frontend /fe/dist /app/frontend/dist

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
# Railway/Fly inject $PORT; default to 8000 locally.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/healthz" || exit 1

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
