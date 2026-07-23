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
import logging
import os
import time
from typing import Optional

from ..decision import deterministic_decision
from ..types import (Action, AgentDecision, CycleState, Policy,
                     ValidatedSnapshot)

log = logging.getLogger("cedar.reason")

# Reasoning provider. Groq (OpenAI-compatible, open Llama models) is the default:
# fast and very cheap, which suits this small structured-JSON decision. Set
# CEDAR_LLM_PROVIDER=anthropic (+ ANTHROPIC_API_KEY) to use Claude instead.
PROVIDER = os.getenv("CEDAR_LLM_PROVIDER", "groq").lower()
_DEFAULT_MODEL = {
    "groq": "llama-3.3-70b-versatile",   # cheaper still: llama-3.1-8b-instant
    "anthropic": "claude-haiku-4-5",
}
MODEL = os.getenv("CEDAR_MODEL", "") or _DEFAULT_MODEL.get(PROVIDER, "llama-3.3-70b-versatile")
# Output tokens are the dominant per-call cost; the decision JSON is small.
MAX_TOKENS = int(os.getenv("CEDAR_MAX_TOKENS", "512"))


def _api_key_present() -> bool:
    """Is the active provider's key configured?"""
    return bool(os.getenv("GROQ_API_KEY") if PROVIDER == "groq"
                else os.getenv("ANTHROPIC_API_KEY"))
# When enabled (default), Claude is only called when the deterministic pre-check
# sees an actionable reallocation candidate. Clear HOLDs (no APY delta over the
# policy threshold) skip the LLM entirely -- most cycles, in practice.
LLM_GATE = os.getenv("CEDAR_LLM_GATE", "1") == "1"

SYSTEM_PROMPT = """You are a yield-routing decision engine. You will be given:
1. A validated market snapshot (pool APYs, current allocation, gas estimate)
2. The active policy (min APY delta, max reallocation %, allowed pools)
3. Optionally, a plain-English MANDATE: a standing instruction from the operator.

You must decide: HOLD or REALLOCATE.
You may ONLY reference pools and values present in the snapshot provided.

A non-LLM recheck enforces a SAFETY ENVELOPE on whatever you propose — it does
NOT dictate the exact move, but it WILL block anything unsafe. Your move must:
- go from a pool that currently holds funds, to a DIFFERENT allowed pool,
- move to a pool with a STRICTLY HIGHER APY (never into a worse-yielding pool),
- clear the policy's min APY delta on that edge,
- move no more than max_reallocation_pct of total_value (you may move LESS).

Within that envelope you have judgment. Default behavior (no mandate) is to
capture the best available edge: from the lowest-APY held pool to the highest-APY
allowed pool. But if a MANDATE is present, HONOR IT — e.g. it may ask you to stay
conservative, keep a minimum in a pool for diversification, move partial amounts,
prefer a specific pool, or avoid small edges. Apply the mandate as long as the
result still satisfies the safety envelope above; if the mandate would require an
unsafe move, HOLD instead and say why.

Justify your decision citing the specific figures given (and the mandate, if any).
reasoning_trace rules: 2 to 4 short plain-English sentences. No brackets,
no markdown, no formulas or arrow notation - write it so a non-technical
reader can follow the decision.
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
        "mandate": policy.mandate or "(none — capture the best available edge)",
    }, indent=2)


def _parse_decision(text: str) -> AgentDecision:
    text = text.strip()
    if text.startswith("```"):                       # tolerate code fences
        text = text.strip("`")
        text = text[text.find("{"):text.rfind("}") + 1]
    return AgentDecision.model_validate(json.loads(text))


def _call_groq(snap: ValidatedSnapshot, policy: Policy) -> AgentDecision:
    from groq import Groq

    client = Groq()  # reads GROQ_API_KEY
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0,
        response_format={"type": "json_object"},     # guarantees valid JSON
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _snapshot_payload(snap, policy)},
        ],
    )
    return _parse_decision(resp.choices[0].message.content or "")


def _call_anthropic(snap: ValidatedSnapshot, policy: Policy) -> AgentDecision:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _snapshot_payload(snap, policy)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return _parse_decision(text)


def _call_llm(snap: ValidatedSnapshot, policy: Policy) -> AgentDecision:
    if PROVIDER == "anthropic":
        return _call_anthropic(snap, policy)
    return _call_groq(snap, policy)


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
    if not _trace_numbers_grounded(decision.reasoning_trace, snap, policy, decision):
        return force_hold("reasoning_trace cites a figure not present in the snapshot")

    return decision


def _trace_numbers_grounded(trace: str, snap: ValidatedSnapshot,
                            policy: Policy,
                            decision: Optional[AgentDecision] = None) -> bool:
    """Fabrication check, targeted at APY-style claims.

    The dangerous fabrication is an invented *pool APY* ("PoolB APY is 42.7%").
    Only numbers presented as percentages are scrutinised; each must be one of:
      - a known pool APY or policy percentage,
      - a difference of two known APYs (a legitimate delta),
      - a portfolio share: any allocation / total, or the decision's own
        amount / total (e.g. "moving 150 (15% of portfolio)").
    Derived quantities that are NOT percentages (e.g. an annual-gain estimate
    ``apy*amount``) are legitimate model arithmetic and are allowed — grounding
    of the actual action is enforced separately by the pool/amount/cap checks
    and the deterministic RECHECK.
    """
    import re

    known_apys = {round(r.apy, 3) for r in snap.pools.values()}
    known_pcts = set(known_apys) | {round(policy.min_apy_delta, 3),
                                    round(policy.max_reallocation_pct, 3)}
    # figures the operator wrote into the mandate are legitimate to cite
    for mm in re.finditer(r"\d+\.?\d*", policy.mandate or ""):
        known_pcts.add(round(float(mm.group()), 3))
    # legitimate pairwise APY deltas (e.g. "delta 8.744%")
    deltas = {round(abs(a - b), 3) for a in known_apys for b in known_apys}
    # legitimate portfolio shares (allocation/total, decision amount/total)
    shares: set[float] = set()
    total = snap.total_value
    if total > 0:
        amounts = [r.allocation for r in snap.pools.values()]
        if decision is not None and decision.amount:
            amounts.append(decision.amount)
        for amt in amounts:
            shares.add(round(amt / total * 100.0, 3))

    for m in re.finditer(r"(\d+\.?\d*)\s*%", trace):
        val = round(float(m.group(1)), 3)
        if val in known_pcts:
            continue
        if any(abs(val - d) < 0.05 for d in deltas):
            continue
        if any(abs(val - s) < 0.05 for s in shares):
            continue
        return False
    return True


def _plain_llm_error(exc: Exception) -> str:
    """One short, human-readable reason for a failed model call."""
    s = str(exc).lower()
    if "credit" in s or "quota" in s or "billing" in s:
        return "the reasoning account is out of credits"
    if "rate_limit" in s or "rate limit" in s or "429" in s:
        return "the API rate limit was hit"
    if "overloaded" in s or "503" in s or "529" in s:
        return "the API is temporarily overloaded"
    if "authentication" in s or "invalid api key" in s or "401" in s:
        return "the API key was rejected"
    return exc.__class__.__name__


def _annotate_provenance(decision: AgentDecision, snap: ValidatedSnapshot) -> AgentDecision:
    """Prepend the data-provenance note so single-source/unverified cycles are
    visible in the reasoning trace, never silently passed."""
    decision.reasoning_trace = f"[{snap.provenance_note()}] {decision.reasoning_trace}"
    return decision


def make_reason_node(force_deterministic: bool = False, cooldown_provider=None,
                     budget_store=None):
    """Build the reason node.

    ``cooldown_provider``  -> callable returning the last EXECUTED timestamp (or
        None). While a cooldown is still active a reallocation cannot actuate, so
        the model call is skipped -- reasoning we could not act on is wasted spend.
    ``budget_store``       -> object exposing ``llm_calls_today()`` and
        ``incr_llm_call()``; enforces ``CEDAR_LLM_DAILY_BUDGET`` calls/day.
    """
    def _in_cooldown(policy) -> bool:
        if cooldown_provider is None:
            return False
        cd = getattr(policy, "cooldown_seconds", 0) or 0
        if cd <= 0:
            return False
        last = cooldown_provider()
        return last is not None and (time.time() - last) < cd

    def _budget_left() -> bool:
        limit = int(os.getenv("CEDAR_LLM_DAILY_BUDGET", "0") or "0")
        if limit <= 0 or budget_store is None:
            return True
        return budget_store.llm_calls_today() < limit

    def reason(state: CycleState) -> CycleState:
        snap = state["validated"]
        policy = state["policy"]

        use_llm = (not force_deterministic) and _api_key_present()

        # Credit-saving gates: consult the model ONLY when capital might actually
        # move this cycle. We skip the API call when (a) the deterministic engine
        # sees no actionable move, (b) a cooldown means we could not actuate even
        # if it did, or (c) the daily model-call budget is spent.
        if use_llm and LLM_GATE:
            pre = deterministic_decision(snap, policy)
            if pre.action == Action.HOLD:
                pre.reasoning_trace = (
                    "No pool clears the policy's minimum APY delta, so there is "
                    "nothing to reallocate this cycle. The model call was skipped "
                    "to save API credits. " + pre.reasoning_trace)
                return {"agent_decision": _annotate_provenance(pre, snap)}
            if _in_cooldown(policy):
                pre.reasoning_trace = (
                    "A reallocation is warranted, but the post-move cooldown is "
                    "still active so nothing can execute yet. The model call was "
                    "skipped to save API credits; the cooldown guardrail will hold "
                    "this cycle. " + pre.reasoning_trace)
                return {"agent_decision": _annotate_provenance(
                    _sanitize(pre, snap, policy), snap)}
            if not _budget_left():
                pre.reasoning_trace = (
                    "The daily model-call budget is spent, so the deterministic "
                    "engine decided this cycle to protect the API key. "
                    + pre.reasoning_trace)
                return {"agent_decision": _annotate_provenance(
                    _sanitize(pre, snap, policy), snap)}

        if use_llm:
            try:
                if budget_store is not None:
                    budget_store.incr_llm_call()
                raw = _call_llm(snap, policy)
            except Exception as exc:  # noqa: BLE001  -- never crash the loop on LLM error
                # Full error goes to the server log; the trace stays plain-English.
                log.warning("LLM call failed; deterministic engine decided: %s", exc)
                reason_txt = _plain_llm_error(exc)
                fallback = deterministic_decision(snap, policy)
                fallback.reasoning_trace = (
                    f"The model could not be reached ({reason_txt}), so the "
                    f"deterministic engine decided this cycle. {fallback.reasoning_trace}")
                return {"agent_decision": _annotate_provenance(fallback, snap)}
        else:
            raw = deterministic_decision(snap, policy)
            if not force_deterministic:
                raw.reasoning_trace = (
                    "No model API key is configured, so the deterministic engine "
                    "decided this cycle. " + raw.reasoning_trace)

        return {"agent_decision": _annotate_provenance(_sanitize(raw, snap, policy), snap)}

    return reason
