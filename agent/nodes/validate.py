"""VALIDATE node: the hallucination / bad-data guardrail.

Checks, in order:
  1. Range   -- every APY within [apy_min_bound, apy_max_bound]
  2. Freshness -- snapshot timestamp within freshness_seconds of now
  3. Cross-source consistency -- Casper MCP vs CSPR.trade APY within tolerance;
     on divergence we HALT (do not average).

Pass -> ValidatedSnapshot in state. Fail -> ValidationFailure (graph routes
straight to LOG:HOLD with a specific reason).
"""
from __future__ import annotations

import time

from ..types import CycleState, ValidatedSnapshot, ValidationFailure


def validate(state: CycleState) -> CycleState:
    snap = state["snapshot"]
    policy = state["policy"]

    # 1. Range check
    for pid, reading in snap.pools.items():
        if not (policy.apy_min_bound <= reading.apy <= policy.apy_max_bound):
            return {
                "validation_failure": ValidationFailure(
                    reason="data validation failed",
                    detail=(f"APY out of bounds for {pid}: {reading.apy}% not in "
                            f"[{policy.apy_min_bound}, {policy.apy_max_bound}]"),
                )
            }

    # 2. Freshness check
    age = time.time() - snap.timestamp
    if age > policy.freshness_seconds:
        return {
            "validation_failure": ValidationFailure(
                reason="data validation failed",
                detail=f"stale snapshot: age {age:.1f}s > {policy.freshness_seconds}s",
            )
        }

    # 3a. Cross-source APY consistency (second APY provider, when present)
    for pid, reading in snap.pools.items():
        other = snap.cross_source_apy.get(pid)
        if other is None:
            continue
        if abs(other - reading.apy) > policy.cross_source_tolerance:
            return {
                "validation_failure": ValidationFailure(
                    reason="data validation failed",
                    detail=(f"cross-source APY divergence for {pid}: {reading.apy}% "
                            f"vs {other}% exceeds {policy.cross_source_tolerance}pp"),
                )
            }

    # 3b. Cross-source PRICE consistency (CSPR.trade reserves vs cspr.cloud DEX
    # rate) — real two-provider integrity check; runs only when cspr.cloud has a
    # rate for the pool's tokens (else the pool is absent from cross_source_price).
    for pid, second in snap.cross_source_price.items():
        primary = snap.implied_price.get(pid)
        if primary is None or primary <= 0 or second <= 0:
            continue
        divergence_pct = abs(primary - second) / primary * 100.0
        if divergence_pct > policy.cross_source_tolerance:
            return {
                "validation_failure": ValidationFailure(
                    reason="data validation failed",
                    detail=(f"cross-source PRICE divergence for {pid}: cspr_trade "
                            f"{primary:.6f} vs cspr_cloud {second:.6f} "
                            f"({divergence_pct:.2f}% > {policy.cross_source_tolerance}%)"),
                )
            }

    validated = ValidatedSnapshot(**snap.model_dump())
    return {"validated": validated}
