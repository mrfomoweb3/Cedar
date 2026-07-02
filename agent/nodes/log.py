"""LOG node: runs on EVERY terminal path and writes the full cycle record.

This single record powers both the Dashboard live feed and the Audit Log.
Also resolves the final ``outcome`` for the paths that didn't set one
(validation failure, HOLD decision, blocked-by-guardrail/recheck).
"""
from __future__ import annotations

import json
import time
from typing import Callable

from ..types import Action, CycleState, Outcome


def make_log_node(record_cycle: Callable[[dict], None]):

    def log(state: CycleState) -> CycleState:
        finished = time.time()
        decision = state.get("agent_decision")
        snap = state.get("validated") or state.get("snapshot")

        outcome = state.get("outcome")
        hold_reason = state.get("hold_reason", "")

        if outcome is None:
            # Resolve outcome for non-actuate paths.
            if "validation_failure" in state:
                outcome = Outcome.VALIDATION_FAILED
                hold_reason = state["validation_failure"].detail
            elif decision is None or decision.action == Action.HOLD:
                outcome = Outcome.HOLD
                hold_reason = hold_reason or (decision.reasoning_trace if decision else "hold")
            elif not state.get("recheck_agrees", True):
                outcome = Outcome.BLOCKED
                hold_reason = "recheck disagreement: deterministic engine != agent"
            else:
                # REALLOCATE that reached log without EXECUTED => a guardrail blocked it.
                failed = [g for g in state.get("guardrail_results", []) if not g.passed]
                outcome = Outcome.BLOCKED
                hold_reason = (f"guardrail '{failed[0].name}': {failed[0].detail}"
                               if failed else "blocked before actuation")

        record = {
            "id": state["cycle_id"],
            "started_at": state.get("started_at", finished),
            "finished_at": finished,
            "outcome": outcome.value,
            "action": decision.action.value if decision else None,
            "from_pool": decision.from_pool if decision else None,
            "to_pool": decision.to_pool if decision else None,
            "amount": decision.amount if decision else None,
            "confidence": decision.confidence if decision else None,
            "reasoning": decision.reasoning_trace if decision else None,
            "recheck_agrees": 1 if state.get("recheck_agrees") else 0,
            "hold_reason": hold_reason,
            "tx_hash": state.get("tx_hash"),
            "snapshot_json": snap.model_dump_json() if snap else None,
            "guardrails_json": json.dumps([g.model_dump() for g in
                                           state.get("guardrail_results", [])]),
        }
        record_cycle(record)
        return {"outcome": outcome, "hold_reason": hold_reason, "finished_at": finished}

    return log
