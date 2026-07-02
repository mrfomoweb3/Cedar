# Cedar — Deploying Online

Cedar has two deployables: the **backend** (FastAPI + the in-process autonomous
scheduler) and the **frontend** (static dashboard). Storage is Postgres in the
cloud (set `DATABASE_URL`) and SQLite locally.

> **One hard rule:** run the backend with a **single worker / single instance**.
> The scheduler is a background thread inside the process; N workers = N
> autonomous loops all signing transactions. The Dockerfile and `render.yaml`
> already pin this — don't override it.

## Storage

Backend-agnostic via SQLAlchemy (`api/store.py`):
- `DATABASE_URL` set → that Postgres database (verified on Postgres 16).
- otherwise → local SQLite at `CEDAR_DB`.

`postgres://` / `postgresql://` URLs are auto-normalized to the psycopg3 driver.
Schema is created on startup; no migration step.

## Secrets (never commit these)

Provide as host env vars:

| Var | Needed when | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude reasoning | else falls back to the deterministic engine |
| `CSPR_CLOUD_API_KEY` | Casper MCP 2nd source | from cspr.cloud |
| `CASPER_SECRET_KEY_B64` | `CEDAR_SIGNER=casper` | base64 of `secret_key.pem`; decoded to a file at startup by `agent/config.py` |

```bash
# produce the base64 signing key for the host:
base64 -i "Account 1_secret_key.pem" | tr -d '\n'   # paste as CASPER_SECRET_KEY_B64
```

## Runtime posture

| `CEDAR_DATA_SOURCE` | `CEDAR_SIGNER` | Behaviour |
|---|---|---|
| `casper` | `mock` | **recommended public default** — real MCP reads + Claude, simulated actuation (no CSPR spent, no key needed) |
| `casper` | `casper` | fully live — real on-chain reallocations (needs `CASPER_SECRET_KEY_B64`, spends testnet CSPR) |
| `mock` | `mock` | offline demo — enables the Spike/Bad-Data buttons |

## Option A — Render (turnkey: DB + API in one blueprint)

1. Push this repo to GitHub.
2. Render Dashboard → **New → Blueprint** → select the repo. It reads
   [`render.yaml`](render.yaml): provisions Postgres + the API (Docker, health-checked).
3. Set the secret env vars (`ANTHROPIC_API_KEY`, `CSPR_CLOUD_API_KEY`, and
   `CASPER_SECRET_KEY_B64` if actuating) in the service's Environment tab.
4. API comes up at `https://cedar-api.onrender.com` — check `/healthz`.

> Free web services sleep after ~15 min idle, which **pauses the autonomous
> loop**. For genuine 24/7 autonomy use a paid instance, or ping `/healthz`
> every few minutes from an uptime monitor.

## Option B — Docker anywhere (Fly.io, Railway, a VPS)

```bash
docker build -t cedar-api .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/cedar" \
  -e CEDAR_DATA_SOURCE=casper -e CEDAR_SIGNER=mock \
  -e ANTHROPIC_API_KEY=... -e CSPR_CLOUD_API_KEY=... \
  -e VAULT_ROUTER_HASH=hash-dc10056192be60ae8db84e0b24e27629aec44381ba41b3bebfc89501b1828135 \
  cedar-api
```

Fly.io: `fly launch` (detects the Dockerfile), `fly postgres create` + `fly postgres attach`
(sets `DATABASE_URL`), `fly secrets set ANTHROPIC_API_KEY=… CSPR_CLOUD_API_KEY=…`,
scale to exactly one machine (`fly scale count 1`).

## Frontend (static)

Any static host. Set `VITE_API_BASE` to the deployed API URL at build time.

**Netlify** (uses `frontend/netlify.toml`, includes SPA fallback):
```bash
cd frontend && VITE_API_BASE=https://cedar-api.onrender.com npm run build
# drag frontend/dist to Netlify, or connect the repo with base dir = frontend
```

**Vercel** (uses `frontend/vercel.json`): import the repo, root = `frontend`,
add `VITE_API_BASE` env var.

SPA routing (`/portfolio`, `/guardrails`, …) is handled by `netlify.toml`,
`vercel.json`, and `public/_redirects` — all three ship a catch-all rewrite to
`index.html`. CORS on the API is open by default; restrict with
`CEDAR_CORS_ORIGINS=https://your-dashboard.example` once the frontend URL is known.

## Post-deploy checklist

- [ ] `GET /healthz` returns `{"ok": true, "db": "postgres", ...}`
- [ ] `GET /agent/status` shows the loop `observing`/`idle` with a ticking countdown
- [ ] Dashboard loads and the live feed populates within one interval
- [ ] Guardrails screen shows the data-provenance card
- [ ] If `CEDAR_SIGNER=casper`: a cycle produces a tx hash that resolves on testnet.cspr.live
