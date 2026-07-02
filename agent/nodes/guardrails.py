"""GUARDRAILS node (non-LLM): final gate before actuation.

Runs only if action == REALLOCATE and recheck agrees. Checks short-circuit on
first failure, each producing a named GuardrailResult:
  1. Cooldown      -- enough time since last reallocation?
  2. Position cap  -- amount within max-% per cycle?
  3. Cost check    -- gas + slippage still leaves a net-positive move over horizon?
  4. Anomaly recheck -- final sanity pass on the numbers (cheap insurance).

Any failure -> outcome BLOCKED with the specific guardrail name + reason.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from ..types import Action, CycleState, GuardrailResult


def make_guardrails_node(last_reallocation_provider: Callable[[], Optional[float]]):

    def guardrails(state: CycleState) -> CycleState:
        decision = state["agent_decision"]
        snap = state["validated"]
        policy = state["policy"]
        results: list[GuardrailResult] = []

        # Only reached for REALLOCATE + agreeing recheck, but be defensive.
        if decision.action != Action.REALLOCATE:
            return {"guardrail_results": results}

        # 1. Cooldown
        last = last_reallocation_provider()
        if last is not None:
            elapsed = time.time() - last
            if elapsed < policy.cooldown_seconds:
                results.append(GuardrailResult(
                    name="cooldown", passed=False,
                    detail=(f"only {elapsed:.0f}s since last reallocation; "
                            f"cooldown is {policy.cooldown_seconds:.0f}s")))
                return {"guardrail_results": results}
        results.append(GuardrailResult(name="cooldown", passed=True,
                                       detail="cooldown satisfied"))

        # 2. Position cap
        max_amount = snap.total_value * (policy.max_reallocation_pct / 100.0)
        if (decision.amount or 0) > max_amount + 1e-9:
            results.append(GuardrailResult(
                name="position_cap", passed=False,
                detail=(f"amount {decision.amount} exceeds cap "
                        f"{policy.max_reallocation_pct}% (= {max_amount:.4f})")))
            return {"guardrail_results": results}
        results.append(GuardrailResult(name="position_cap", passed=True,
                                       detail=f"amount within cap {max_amount:.4f}"))

        # 3. Cost check: does the APY gain over the hold period beat gas+slippage?
        from_apy = snap.pools[decision.from_pool].apy
        to_apy = snap.pools[decision.to_pool].apy
        delta_pct = (to_apy - from_apy) / 100.0
        amount = decision.amount or 0.0
        horizon = policy.hold_period_days / 365.0
        expected_gain = amount * delta_pct * horizon
        cost = snap.gas_estimate + amount * (policy.expected_slippage_pct / 100.0)
        if expected_gain <= cost:
            results.append(GuardrailResult(
                name="cost_check", passed=False,
                detail=(f"expected gain {expected_gain:.6f} CSPR over "
                        f"{policy.hold_period_days:.0f}d <= cost {cost:.6f} CSPR "
                        f"(gas {snap.gas_estimate} + slippage)")))
            return {"guardrail_results": results}
        results.append(GuardrailResult(
            name="cost_check", passed=True,
            detail=f"expected gain {expected_gain:.6f} > cost {cost:.6f} CSPR"))

        # 4. Anomaly recheck (redundant with Validate by design)
        anomalous = any(not (policy.apy_min_bound <= r.apy <= policy.apy_max_bound)
                        for r in snap.pools.values())
        if anomalous:
            results.append(GuardrailResult(
                name="anomaly_recheck", passed=False,
                detail="an APY fell outside sane bounds on final pass"))
            return {"guardrail_results": results}
        results.append(GuardrailResult(name="anomaly_recheck", passed=True,
                                       detail="numbers within bounds"))

        return {"guardrail_results": results}

    return guardrails
