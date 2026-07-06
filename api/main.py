"""FastAPI app serving the Cedar dashboard + control plane.

Endpoints (Section 7 of the build spec):
  GET  /agent/status        current state + next-cycle countdown
  GET  /agent/feed          recent cycle log entries (Dashboard feed)
  GET  /agent/portfolio     current allocation across pools + total value
  GET  /agent/guardrails    guardrail config + trigger counts + history
  GET  /agent/audit         full paginated audit log
  GET  /agent/policy        current active policy
  POST /agent/policy        update policy (Settings)
  POST /agent/pause         kill switch
  POST /agent/resume        resume loop
  POST /agent/onboard       initial policy setup + wallet connect
  POST /agent/run-once      run a single cycle now (demo control)
  POST /agent/demo/{name}   seed a demo scenario (spike / bad-data)
"""
from __future__ import annotations

import hmac
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.config import load_env

load_env()  # load .env before reading any CEDAR_*/CASPER_* config below

from agent.cspr_click import explorer_url, get_default_signer
from agent.graph import build_default_agent
from agent.mcp_clients import MockMarketDataSource, get_default_source
from agent.scheduler import Scheduler
from agent.types import POOL_IDS, Policy
from api.store import get_store

INTERVAL = float(os.getenv("CEDAR_INTERVAL", "120"))
AUTO_START = os.getenv("CEDAR_AUTOSTART", "1") == "1"

store = get_store()
# Keep a handle on the source so demo endpoints can seed scenarios when mock.
_source = get_default_source()
_signer = get_default_signer()
_agent = build_default_agent(store, source=_source, signer=_signer)
scheduler = Scheduler(_agent, store, interval_seconds=INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logging.getLogger("cedar").info(
        "Cedar starting: data_source=%s signer=%s db=%s interval=%ss autostart=%s",
        os.getenv("CEDAR_DATA_SOURCE", "mock"), os.getenv("CEDAR_SIGNER", "mock"),
        "postgres" if os.getenv("DATABASE_URL") else "sqlite", INTERVAL, AUTO_START)
    if AUTO_START and not store.is_paused():
        scheduler.start()
    yield
    scheduler.stop()


# Relocate FastAPI's auto-generated API docs off "/docs" so the SPA's own /docs
# page (served by the catch-all) isn't shadowed by Swagger UI. The interactive
# API docs remain available at /api-docs (Swagger) and /api-redoc (ReDoc).
app = FastAPI(title="Cedar Agent API", version="1.0.0", lifespan=lifespan,
              docs_url="/api-docs", redoc_url="/api-redoc")
# CORS: default open (public read-only demo). Restrict via CEDAR_CORS_ORIGINS
# (comma-separated) in production if you expose the write endpoints.
_origins = os.getenv("CEDAR_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",")],
    allow_methods=["*"], allow_headers=["*"])


# --- admin gate for state-changing endpoints ------------------------------
# When CEDAR_ADMIN_TOKEN is set, the write/control endpoints require it (sent as
# `Authorization: Bearer <token>` or `X-Admin-Token: <token>`). When it is unset
# the endpoints stay open, so local dev and the interactive public demo are
# unaffected. Set the token to make a real-signing production deploy read-only
# to the public while the owner still drives it via authenticated calls.
def require_admin(authorization: str = Header(default=""),
                  x_admin_token: str = Header(default="")):
    token = os.getenv("CEDAR_ADMIN_TOKEN", "").strip()
    if not token:
        return  # open when no token is configured
    supplied = x_admin_token.strip()
    if not supplied and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not (supplied and hmac.compare_digest(supplied, token)):
        raise HTTPException(401, "admin token required")


@app.get("/healthz")
def healthz():
    """Liveness/readiness probe for the host. Confirms the DB is reachable."""
    try:
        cycles = store.count_cycles()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"store unavailable: {exc}")
    return {
        "ok": True,
        "db": "postgres" if os.getenv("DATABASE_URL") else "sqlite",
        "data_source": os.getenv("CEDAR_DATA_SOURCE", "mock"),
        "signer": os.getenv("CEDAR_SIGNER", "mock"),
        "paused": store.is_paused(),
        "total_cycles": cycles,
    }


# --- models ---------------------------------------------------------------
class OnboardRequest(BaseModel):
    policy: Policy
    wallet_address: Optional[str] = None


# --- read endpoints -------------------------------------------------------
@app.get("/agent/status")
def status():
    next_at = store.get_next_cycle_at()
    return {
        "status": "paused" if store.is_paused() else store.get_status(),
        "paused": store.is_paused(),
        "next_cycle_at": next_at,
        "next_cycle_in": max(0.0, next_at - time.time()) if next_at else None,
        "interval_seconds": INTERVAL,
        "total_cycles": store.count_cycles(),
    }


@app.get("/agent/feed")
def feed(limit: int = Query(50, le=200)):
    rows = store.feed(limit=limit)
    for r in rows:
        if r.get("tx_hash"):
            r["explorer_url"] = explorer_url(r["tx_hash"])
    return {"cycles": rows}


@app.get("/agent/portfolio")
def portfolio():
    allocs = store.get_allocations()
    total = sum(allocs.values())
    return {
        "allocations": allocs,
        "total_value": total,
        "weights": {p: (allocs.get(p, 0) / total if total else 0) for p in POOL_IDS},
    }


@app.get("/agent/guardrails")
def guardrails():
    policy = store.get_policy()
    return {
        "config": {
            "cooldown_seconds": policy.cooldown_seconds,
            "max_reallocation_pct": policy.max_reallocation_pct,
            "min_apy_delta": policy.min_apy_delta,
            "apy_bounds": [policy.apy_min_bound, policy.apy_max_bound],
            "cross_source_tolerance": policy.cross_source_tolerance,
        },
        "trigger_counts": store.guardrail_trigger_counts(),
        "blocked_history": store.feed(limit=50, outcome="BLOCKED"),
        "cross_source": _cross_source_status(),
    }


def _cross_source_status() -> dict:
    """Data-provenance status from the most recent cycle: is the price cross-check
    corroborated by a second provider, or is the agent running single-source?"""
    recent = store.feed(limit=1)
    default = {"verified": False, "verified_pools": 0, "total_pools": 0,
               "single_source": True,
               "note": "no cycles yet",
               "detail": "Cross-source price verification requires a second provider "
                         "(cspr.cloud) that indexes the active pools' tokens."}
    if not recent or not recent[0].get("snapshot"):
        return default
    snap = recent[0]["snapshot"]
    verified_map = snap.get("cross_source_verified") or {}
    total = len(verified_map)
    verified = sum(1 for v in verified_map.values() if v)
    single = verified == 0
    if total == 0:
        note = "single-source (no cross-source data)"
    elif verified == total:
        note = f"cross-source VERIFIED ({verified}/{total} pools)"
    elif single:
        note = f"single-source, UNVERIFIED (0/{total} pools corroborated)"
    else:
        note = f"partially verified ({verified}/{total} pools)"
    return {
        "verified": verified == total and total > 0,
        "verified_pools": verified,
        "total_pools": total,
        "single_source": single,
        "note": note,
        "detail": ("CSPR.trade price readings are corroborated by cspr.cloud DEX rates "
                   "where indexed. On testnet, cspr.cloud does not index these test-token "
                   "pools, so readings are single-source and shown as UNVERIFIED — not "
                   "silently trusted."),
    }


@app.get("/agent/audit")
def audit(limit: int = Query(50, le=200), offset: int = 0,
          outcome: Optional[str] = None):
    rows = store.feed(limit=limit, offset=offset, outcome=outcome)
    for r in rows:
        if r.get("tx_hash"):
            r["explorer_url"] = explorer_url(r["tx_hash"])
    return {
        "total": store.count_cycles(outcome=outcome),
        "limit": limit,
        "offset": offset,
        "cycles": rows,
    }


@app.get("/agent/policy")
def get_policy():
    return store.get_policy().model_dump()


# --- write endpoints ------------------------------------------------------
@app.post("/agent/policy", dependencies=[Depends(require_admin)])
def set_policy(policy: Policy):
    store.set_policy(policy)
    return {"ok": True, "policy": policy.model_dump()}


@app.post("/agent/pause", dependencies=[Depends(require_admin)])
def pause():
    store.set_paused(True)
    store.set_status("paused")
    return {"ok": True, "paused": True}


@app.post("/agent/resume", dependencies=[Depends(require_admin)])
def resume():
    store.set_paused(False)
    store.set_status("idle")
    scheduler.start()
    return {"ok": True, "paused": False}


@app.post("/agent/onboard", dependencies=[Depends(require_admin)])
def onboard(req: OnboardRequest):
    store.set_policy(req.policy)
    store.set_paused(False)
    scheduler.start()
    return {"ok": True, "policy": req.policy.model_dump(),
            "wallet_address": req.wallet_address}


@app.post("/agent/run-once", dependencies=[Depends(require_admin)])
def run_once():
    state = scheduler.run_once()
    return {"ok": True, "cycle_id": state["cycle_id"],
            "outcome": state["outcome"].value, "tx_hash": state.get("tx_hash")}


@app.post("/agent/demo/{name}", dependencies=[Depends(require_admin)])
def demo(name: str):
    """Seed a controlled demo scenario against the mock data source."""
    if not isinstance(_source, MockMarketDataSource):
        raise HTTPException(400, "demo scenarios require the mock data source")
    if name == "spike":
        _source.spike("PoolB", 20.0)
        return {"ok": True, "seeded": "PoolB APY spiked to 20% (expect REALLOCATE)"}
    if name == "bad-data":
        _source.inject_bad_reading("PoolA", 9000.0)
        return {"ok": True, "seeded": "PoolA APY=9000% (expect VALIDATION_FAILED)"}
    if name == "divergence":
        _source.inject_cross_divergence("PoolC", 25.0)
        return {"ok": True, "seeded": "cross-source divergence on PoolC (expect VALIDATION_FAILED)"}
    raise HTTPException(404, f"unknown demo scenario: {name}")


# --- static dashboard (optional; single-service deploy) -------------------
# If a built frontend is present (FRONTEND_DIST, default ./frontend/dist), serve
# it from this same service so Railway/Fly can host API + dashboard on one URL,
# no CORS. Registered LAST so it never shadows the /agent/* or /healthz routes.
# Skipped entirely when the build isn't present (tests, API-only deploys).
def _mount_frontend() -> None:
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    dist = os.getenv("FRONTEND_DIST",
                     os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
    index = os.path.join(dist, "index.html")
    if not os.path.isfile(index):
        return

    # Hashed assets and other build files.
    app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")),
              name="assets")

    dist_root = os.path.realpath(dist)

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # Never intercept API surface (defensive; those routes match first anyway).
        # NB: "docs" is intentionally NOT excluded — the SPA owns /docs; FastAPI's
        # Swagger UI lives at /api-docs (see the FastAPI() construction above).
        if full_path.startswith(("agent", "healthz", "assets", "api-docs",
                                 "api-redoc", "openapi.json")):
            raise HTTPException(404, "not found")
        # Resolve and confine to the dist root — rejects ../ traversal, absolute
        # paths, and symlink escapes before touching the filesystem.
        candidate = os.path.realpath(os.path.join(dist_root, full_path))
        inside = candidate == dist_root or candidate.startswith(dist_root + os.sep)
        if full_path and inside and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(index)  # SPA deep-link fallback


_mount_frontend()
