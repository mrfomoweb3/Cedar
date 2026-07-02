# Cedar backend — FastAPI + in-process autonomous scheduler.
# IMPORTANT: run with a SINGLE worker. The scheduler is an in-process background
# thread; N workers would spawn N autonomous loops all signing transactions.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CEDAR_DB=/data/cedar.db

WORKDIR /app

# casper-client is optional in-container: the signer shells out to it only when
# CEDAR_SIGNER=casper. For real on-chain actuation from the container, either set
# CEDAR_SIGNER=mock (default demo) or bake casper-client in via a builder stage.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY agent/ agent/
COPY api/ api/

# Local SQLite fallback path (used only when DATABASE_URL is unset).
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# Single worker — see note above.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
