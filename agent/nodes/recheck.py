"""RECHECK node (non-LLM): independently recompute the decision and compare.

Recomputes HOLD/REALLOCATE from the same ValidatedSnapshot + Policy using the
deterministic engine, then compares direction against the agent's decision. On
disagreement -> force HOLD and flag. Should basically never fire if REASON is
built correctly; it's the last line of defense and a clean demo beat.
"""
from __future__ import annotations

from ..decision import deterministic_decision
from ..types import Action, CycleState


def recheck(state: CycleState) -> CycleState:
    snap = state["validated"]
    policy = state["policy"]
    agent = state["agent_decision"]

    independent = deterministic_decision(snap, policy)

    # Agreement is on the ACTION direction. (Exact amount can differ; the
    # position-cap guardrail bounds it, so we don't require amount equality.)
    agrees = independent.action == agent.action
    # If both say REALLOCATE, also require same direction of movement.
    if agrees and agent.action == Action.REALLOCATE:
        agrees = (independent.from_pool == agent.from_pool
                  and independent.to_pool == agent.to_pool)

    return {"recheck_decision": independent, "recheck_agrees": agrees}
