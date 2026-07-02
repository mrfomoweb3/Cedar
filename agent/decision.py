"""Deterministic decision logic.

This is the intentionally-dumb threshold rule used by the RECHECK node and as
a fallback / reference for the LLM reason node. Given a validated snapshot and
policy, it decides HOLD vs REALLOCATE with no LLM involved.

Rule: find the pool with the largest allocation currently held (the "source")
and the allowed pool with the highest APY (the "target"). If the APY delta
clears policy.min_apy_delta and they differ, propose moving up to
max_reallocation_pct of total value from source to target.
"""
from __future__ import annotations

from .types import Action, AgentDecision, Policy, ValidatedSnapshot


def deterministic_decision(snap: ValidatedSnapshot, policy: Policy) -> AgentDecision:
    allowed = set(policy.allowed_pools)
    pools = {pid: r for pid, r in snap.pools.items() if pid in allowed}
    if not pools:
        return AgentDecision(action=Action.HOLD, confidence=1.0,
                             reasoning_trace="No allowed pools in snapshot.")

    # target = highest APY allowed pool
    target_id = max(pools, key=lambda p: pools[p].apy)
    target_apy = pools[target_id].apy

    # source = the currently-held pool (allocation > 0) with the LOWEST apy,
    # i.e. the worst place our money is sitting.
    held = {pid: r for pid, r in pools.items() if r.allocation > 0}
    if not held:
        return AgentDecision(action=Action.HOLD, confidence=1.0,
                             reasoning_trace="No funds currently allocated.")
    source_id = min(held, key=lambda p: held[p].apy)
    source_apy = held[source_id].apy

    delta = target_apy - source_apy
    if source_id == target_id or delta < policy.min_apy_delta:
        return AgentDecision(
            action=Action.HOLD,
            confidence=1.0,
            reasoning_trace=(
                f"Best APY {target_id} {target_apy}% vs worst-held {source_id} "
                f"{source_apy}%; delta {delta:.3f}pp < threshold {policy.min_apy_delta}pp."
            ),
        )

    total = snap.total_value
    max_amount = total * (policy.max_reallocation_pct / 100.0)
    amount = round(min(held[source_id].allocation, max_amount), 6)
    return AgentDecision(
        action=Action.REALLOCATE,
        from_pool=source_id,
        to_pool=target_id,
        amount=amount,
        confidence=1.0,
        reasoning_trace=(
            f"Move {amount} from {source_id} ({source_apy}%) to {target_id} "
            f"({target_apy}%); delta {delta:.3f}pp >= threshold {policy.min_apy_delta}pp, "
            f"capped at {policy.max_reallocation_pct}% of total {total}."
        ),
    )
