"""ACTUATE node: sign + submit the reallocate tx via CSPR.click.

Reached only when guardrails all pass. On success -> outcome EXECUTED + tx_hash,
and the local allocation cache is updated. On failure -> EXECUTION_FAILED, no
retry within the same cycle (avoid double-spend); surfaced for the next cycle.
"""
from __future__ import annotations

from typing import Callable

from ..cspr_click import Signer
from ..types import CycleState, Outcome


def make_actuate_node(signer: Signer,
                      apply_reallocation: Callable[[str, str, float], None]):

    def actuate(state: CycleState) -> CycleState:
        decision = state["agent_decision"]
        assert decision.from_pool and decision.to_pool and decision.amount
        try:
            tx_hash = signer.reallocate(
                decision.from_pool, decision.to_pool, decision.amount)
        except Exception as exc:  # noqa: BLE001
            return {"outcome": Outcome.EXECUTION_FAILED,
                    "hold_reason": f"execution failed: {exc}",
                    "tx_hash": None}

        apply_reallocation(decision.from_pool, decision.to_pool, decision.amount)
        return {"outcome": Outcome.EXECUTED, "tx_hash": tx_hash}

    return actuate
