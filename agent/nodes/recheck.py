"""RECHECK node (non-LLM): independently validate the proposed move is safe.

The deterministic engine enforces a **safety envelope**, not a single dictated
move: whatever the reasoner proposed must be safe and rational (valid pools,
funds actually held, within the position cap, and a real positive APY edge that
clears the threshold). This lets the LLM apply plain-English-mandate judgment
(partial moves, diversification, an alternative valid target) while the recheck
still hard-vetoes anything unsafe — force HOLD on failure. Last line of defense
and a clean demo beat.
"""
from __future__ import annotations

from ..decision import deterministic_decision, within_safety_envelope
from ..types import CycleState


def recheck(state: CycleState) -> CycleState:
    snap = state["validated"]
    policy = state["policy"]
    agent = state["agent_decision"]

    # The greedy-optimal move, kept for reference/logging and the trace.
    independent = deterministic_decision(snap, policy)

    # Agreement = the agent's proposal sits inside the safety envelope.
    agrees, reason = within_safety_envelope(agent, snap, policy)
    independent.reasoning_trace = f"[recheck] {reason} | greedy: {independent.reasoning_trace}"

    return {"recheck_decision": independent, "recheck_agrees": agrees}
