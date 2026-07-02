"""REASON node: schema-constrained LLM decision over validated data only.

The LLM sees ONLY the validated snapshot + active policy. It cannot browse,
search, or recall. Its JSON output is then hard-checked in code (not by another
LLM) and force-HELD if it references unknown pools, exceeds the position cap, or
cites numbers that aren't in the snapshot (cheap fabrication check).

If no ANTHROPIC_API_KEY is configured, we fall back to the deterministic engine
so the loop still runs offline for demos/tests -- clearly flagged in the trace.
"""
from __future__ import annotations

import json
import os

from ..decision import deterministic_decision
from ..types import (Action, AgentDecision, CycleState, Policy,
                     ValidatedSnapshot)

MODEL = os.getenv("CEDAR_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = """You are a yield-routing decision engine. You will be given:
1. A validated market snapshot (pool APYs, current allocation, gas estimate)
2. The active policy (min APY delta, max reallocation %, cooldown status, allowed pools)

You must decide: HOLD or REALLOCATE.
You may ONLY reference pools and values present in the snapshot provided.
You must justify your decision citing the specific figures given.
Respond ONLY in the following JSON schema, nothing else:

{
  "action": "HOLD" | "REALLOCATE",
  "from_pool": string | null,
  "to_pool": string | null,
  "amount": number | null,
  "confidence": number,
  "reasoning_trace": string
}"""


def _snapshot_payload(snap: ValidatedSnapshot, policy: Policy) -> str:
    return json.dumps({
        "snapshot": {
            "pools": {pid: {"apy": r.apy, "allocation": r.allocation}
                      for pid, r in snap.pools.items()},
            "gas_estimate": snap.gas_estimate,
            "total_value": snap.total_value,
        },
        "policy": {
            "min_apy_delta": policy.min_apy_delta,
            "max_reallocation_pct": policy.max_reallocation_pct,
            "allowed_pools": policy.allowed_pools,
        },
    }, indent=2)


def _call_llm(snap: ValidatedSnapshot, policy: Policy) -> AgentDecision:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _snapshot_payload(snap, policy)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    # tolerate accidental code fences
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):text.rfind("}") + 1]
    data = json.loads(text)
    return AgentDecision.model_validate(data)


def _sanitize(decision: AgentDecision, snap: ValidatedSnapshot,
              policy: Policy) -> AgentDecision:
    """Code-side output handling: force-HOLD on any violation."""
    if decision.action != Action.REALLOCATE:
        return decision

    pool_ids = set(snap.pools.keys())
    allowed = set(policy.allowed_pools)

    def force_hold(reason: str) -> AgentDecision:
        return AgentDecision(
            action=Action.HOLD, confidence=decision.confidence,
            reasoning_trace=f"[force-HOLD] {reason} | original: {decision.reasoning_trace}",
        )

    # unknown / disallowed pools
    if decision.from_pool not in pool_ids or decision.to_pool not in pool_ids:
        return force_hold("references a pool not in the validated snapshot")
    if decision.from_pool not in allowed or decision.to_pool not in allowed:
        return force_hold("references a pool not in the policy allow-list")
    if decision.from_pool == decision.to_pool:
        return force_hold("from_pool == to_pool")
    if decision.amount is None or decision.amount <= 0:
        return force_hold("missing/invalid amount")

    # position cap
    max_amount = snap.total_value * (policy.max_reallocation_pct / 100.0)
    if decision.amount > max_amount + 1e-9:
        return force_hold(
            f"amount {decision.amount} exceeds max {policy.max_reallocation_pct}% "
            f"(= {max_amount}) of total value")

    # fabrication check: every number-looking token in the trace must correspond
    # to a value present in the snapshot/policy (cheap, no second LLM call).
    if not _trace_numbers_grounded(decision.reasoning_trace, snap, policy):
        return force_hold("reasoning_trace cites a figure not present in the snapshot")

    return decision


def _trace_numbers_grounded(trace: str, snap: ValidatedSnapshot,
                            policy: Policy) -> bool:
    """Fabrication check, targeted at APY-style claims.

    The dangerous fabrication is an invented *pool APY* ("PoolB APY is 42.7%").
    Only numbers presented as percentages are scrutinised; each must be a known
    APY, a difference of two known APYs (a legitimate delta), or a known policy
    percentage. Derived quantities that are NOT percentages (e.g. an annual-gain
    estimate ``apy*amount``, or the reallocation amount) are legitimate model
    arithmetic and are allowed — grounding of the actual action is enforced
    separately by the pool/amount/cap checks and the deterministic RECHECK.
    """
    import re

    known_apys = {round(r.apy, 3) for r in snap.pools.values()}
    known_pcts = set(known_apys) | {round(policy.min_apy_delta, 3),
                                    round(policy.max_reallocation_pct, 3)}
    # legitimate pairwise APY deltas (e.g. "delta 8.744%")
    deltas = {round(abs(a - b), 3) for a in known_apys for b in known_apys}

    for m in re.finditer(r"(\d+\.?\d*)\s*%", trace):
        val = round(float(m.group(1)), 3)
        if val in known_pcts:
            continue
        if any(abs(val - d) < 0.05 for d in deltas):
            continue
        return False
    return True


def _annotate_provenance(decision: AgentDecision, snap: ValidatedSnapshot) -> AgentDecision:
    """Prepend the data-provenance note so single-source/unverified cycles are
    visible in the reasoning trace, never silently passed."""
    decision.reasoning_trace = f"[{snap.provenance_note()}] {decision.reasoning_trace}"
    return decision


def make_reason_node(force_deterministic: bool = False):
    def reason(state: CycleState) -> CycleState:
        snap = state["validated"]
        policy = state["policy"]

        use_llm = (not force_deterministic) and bool(os.getenv("ANTHROPIC_API_KEY"))
        if use_llm:
            try:
                raw = _call_llm(snap, policy)
            except Exception as exc:  # noqa: BLE001  -- never crash the loop on LLM error
                fallback = deterministic_decision(snap, policy)
                fallback.reasoning_trace = (
                    f"[llm-error->deterministic] {exc} | {fallback.reasoning_trace}")
                return {"agent_decision": _annotate_provenance(fallback, snap)}
        else:
            raw = deterministic_decision(snap, policy)
            if not force_deterministic:
                raw.reasoning_trace = "[no-api-key->deterministic] " + raw.reasoning_trace

        return {"agent_decision": _annotate_provenance(_sanitize(raw, snap, policy), snap)}

    return reason
