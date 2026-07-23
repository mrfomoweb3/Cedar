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


def within_safety_envelope(
    decision: AgentDecision, snap: ValidatedSnapshot, policy: Policy
) -> tuple[bool, str]:
    """Independent, non-LLM safety check on a *proposed* reallocation.

    Unlike ``deterministic_decision`` (which computes the single greedy-optimal
    move), this validates that whatever move the reasoner proposed is **safe and
    rational** — without requiring it to be the greedy one. That lets the LLM
    exercise mandate-driven judgment (partial moves, diversification, an
    alternative valid target) while the recheck still hard-vetoes anything
    unsafe. Returns ``(ok, reason)``.

    A HOLD is always within the envelope. A REALLOCATE must satisfy ALL of:
      * both pools are in the allow-list and distinct,
      * the source actually holds >= the amount (can't move phantom funds),
      * the amount is positive and within the position cap,
      * the target yields MORE than the source (never move into a worse pool),
      * that APY edge clears ``min_apy_delta``.
    """
    if decision.action != Action.REALLOCATE:
        return True, "hold is always safe"

    allowed = set(policy.allowed_pools)
    frm, to, amount = decision.from_pool, decision.to_pool, decision.amount or 0.0

    if frm not in allowed or to not in allowed:
        return False, f"move touches a non-allow-listed pool ({frm}->{to})"
    if frm == to:
        return False, "source and target pool are the same"
    if frm not in snap.pools or to not in snap.pools:
        return False, "move references a pool absent from the snapshot"
    if amount <= 0:
        return False, "amount is not positive"

    src, tgt = snap.pools[frm], snap.pools[to]
    if src.allocation < amount - 1e-9:
        return False, f"source {frm} holds {src.allocation}, less than {amount}"
    cap = snap.total_value * (policy.max_reallocation_pct / 100.0)
    if amount > cap + 1e-9:
        return False, f"amount {amount} exceeds position cap {cap:.6f}"

    edge = tgt.apy - src.apy
    if edge <= 0:
        return False, f"target {to} ({tgt.apy}%) does not out-yield source {frm} ({src.apy}%)"
    if edge < policy.min_apy_delta:
        return False, f"APY edge {edge:.3f}pp < threshold {policy.min_apy_delta}pp"

    return True, f"safe: {frm}->{to} edge {edge:.3f}pp, amount {amount} within cap"
