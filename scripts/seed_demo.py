"""Seed the two headline demo scenarios and print the resulting cycle outcomes.

Run against a running API:  python scripts/seed_demo.py
Or standalone (no server):  python scripts/seed_demo.py --local
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_local():
    from agent.cspr_click import MockSigner
    from agent.graph import build_default_agent
    from agent.mcp_clients import MockMarketDataSource
    from agent.types import Policy
    from api.store import Store

    store = Store("data/demo.db")
    src = MockMarketDataSource(seed=1)
    agent = build_default_agent(store, force_deterministic=True,
                                source=src, signer=MockSigner())
    policy = Policy(cooldown_seconds=300, hold_period_days=365, min_apy_delta=1.0)

    print("Scenario 1 -- APY spike triggers a real reallocation:")
    src.spike("PoolB", 20.0)
    s = agent.run_cycle(policy)
    print(f"  -> {s['outcome'].value}  tx={s.get('tx_hash')}")

    print("Scenario 2 -- cooldown guardrail visibly blocks the next move:")
    src.spike("PoolC", 25.0)
    s = agent.run_cycle(policy)
    print(f"  -> {s['outcome'].value}  reason={s['hold_reason']}")

    print("Scenario 3 -- bad data blocked by the validation guardrail:")
    src.inject_bad_reading("PoolA", 9000.0)
    s = agent.run_cycle(policy)
    print(f"  -> {s['outcome'].value}  reason={s['hold_reason']}")


def run_remote(base: str):
    import httpx
    for name, expect in [("spike", "EXECUTED"), ("bad-data", "VALIDATION_FAILED")]:
        httpx.post(f"{base}/agent/demo/{name}")
        r = httpx.post(f"{base}/agent/run-once").json()
        print(f"  {name}: {r['outcome']} (expected {expect}) tx={r.get('tx_hash')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="run cycles in-process")
    ap.add_argument("--base", default="http://localhost:8000")
    args = ap.parse_args()
    if args.local:
        run_local()
    else:
        try:
            run_remote(args.base)
        except Exception as exc:  # noqa: BLE001
            print(f"Could not reach API at {args.base}: {exc}", file=sys.stderr)
            print("Tip: start the server, or use --local.", file=sys.stderr)
            sys.exit(1)
