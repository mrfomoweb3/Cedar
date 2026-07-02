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

import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
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
    if AUTO_START and not store.is_paused():
        scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Cedar Agent API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


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
@app.post("/agent/policy")
def set_policy(policy: Policy):
    store.set_policy(policy)
    return {"ok": True, "policy": policy.model_dump()}


@app.post("/agent/pause")
def pause():
    store.set_paused(True)
    store.set_status("paused")
    return {"ok": True, "paused": True}


@app.post("/agent/resume")
def resume():
    store.set_paused(False)
    store.set_status("idle")
    scheduler.start()
    return {"ok": True, "paused": False}


@app.post("/agent/onboard")
def onboard(req: OnboardRequest):
    store.set_policy(req.policy)
    store.set_paused(False)
    scheduler.start()
    return {"ok": True, "policy": req.policy.model_dump(),
            "wallet_address": req.wallet_address}


@app.post("/agent/run-once")
def run_once():
    state = scheduler.run_once()
    return {"ok": True, "cycle_id": state["cycle_id"],
            "outcome": state["outcome"].value, "tx_hash": state.get("tx_hash")}


@app.post("/agent/demo/{name}")
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
