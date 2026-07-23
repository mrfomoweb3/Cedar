"""Segment 4 test gate: recheck agrees across varied cycles; cooldown, position
cap, and cost-check guardrails each block correctly."""
import time

from agent.decision import deterministic_decision
from agent.nodes.guardrails import make_guardrails_node
from agent.nodes.recheck import recheck
from agent.types import (Action, AgentDecision, Policy, ValidatedSnapshot,
                         PoolReading)


def _validated(apy_a=8.0, apy_b=9.0, apy_c=7.0, alloc=(400, 400, 200)):
    pools = {
        "PoolA": PoolReading(pool_id="PoolA", apy=apy_a, allocation=alloc[0]),
        "PoolB": PoolReading(pool_id="PoolB", apy=apy_b, allocation=alloc[1]),
        "PoolC": PoolReading(pool_id="PoolC", apy=apy_c, allocation=alloc[2]),
    }
    return ValidatedSnapshot(pools=pools, gas_estimate=0.1,
                             cross_source_apy={k: v.apy for k, v in pools.items()})


def test_recheck_agrees_over_varied_cycles():
    policy = Policy(min_apy_delta=1.0)
    cases = [(8, 9, 7), (7, 13, 7), (10, 10.2, 10.1), (6, 6, 20), (15, 8, 9)]
    for a, b, c in cases:
        snap = _validated(a, b, c)
        agent = deterministic_decision(snap, policy)
        out = recheck({"validated": snap, "policy": policy, "agent_decision": agent})
        assert out["recheck_agrees"] is True


def test_recheck_allows_hold_and_valid_alternative_moves():
    """The recheck enforces a safety ENVELOPE, not the greedy move: a HOLD is
    always safe, and a valid non-greedy move (e.g. a mandate-driven partial or
    an alternative up-yielding target) is allowed."""
    policy = Policy(min_apy_delta=1.0)
    snap = _validated(7, 13, 9)  # greedy = PoolA->PoolB
    # HOLD is always within the envelope now.
    hold = AgentDecision(action=Action.HOLD, reasoning_trace="conservative hold")
    assert recheck({"validated": snap, "policy": policy,
                    "agent_decision": hold})["recheck_agrees"] is True
    # A different-but-safe target (PoolA->PoolC, still up-yield, clears delta).
    alt = AgentDecision(action=Action.REALLOCATE, from_pool="PoolA", to_pool="PoolC",
                        amount=50.0, reasoning_trace="diversify into PoolC")
    assert recheck({"validated": snap, "policy": policy,
                    "agent_decision": alt})["recheck_agrees"] is True


def test_recheck_vetoes_unsafe_moves():
    """Unsafe reallocations are still hard-blocked (the last line of defense)."""
    policy = Policy(min_apy_delta=1.0)
    snap = _validated(7, 13, 9, alloc=(400, 400, 200))
    # moving INTO a lower-yield pool (PoolB 13% -> PoolC 9%) is irrational
    downhill = AgentDecision(action=Action.REALLOCATE, from_pool="PoolB",
                             to_pool="PoolC", amount=50.0, reasoning_trace="bad")
    assert recheck({"validated": snap, "policy": policy,
                    "agent_decision": downhill})["recheck_agrees"] is False
    # moving more than the source holds
    overdraw = AgentDecision(action=Action.REALLOCATE, from_pool="PoolC",
                             to_pool="PoolB", amount=9999.0, reasoning_trace="bad")
    assert recheck({"validated": snap, "policy": policy,
                    "agent_decision": overdraw})["recheck_agrees"] is False


def test_cooldown_blocks_recent_reallocation():
    snap = _validated(7, 13, 7)
    policy = Policy(cooldown_seconds=300)
    decision = deterministic_decision(snap, policy)
    gr = make_guardrails_node(lambda: time.time() - 10)  # 10s ago
    out = gr({"validated": snap, "policy": policy, "agent_decision": decision})
    failed = [g for g in out["guardrail_results"] if not g.passed]
    assert failed and failed[0].name == "cooldown"


def test_position_cap_blocks_oversized():
    snap = _validated(7, 13, 7)
    policy = Policy(max_reallocation_pct=25.0, cooldown_seconds=0)
    decision = AgentDecision(action=Action.REALLOCATE, from_pool="PoolA",
                             to_pool="PoolB", amount=900, confidence=1.0,
                             reasoning_trace="oversized")
    gr = make_guardrails_node(lambda: None)
    out = gr({"validated": snap, "policy": policy, "agent_decision": decision})
    failed = [g for g in out["guardrail_results"] if not g.passed]
    assert failed and failed[0].name == "position_cap"


def test_cost_check_blocks_when_gas_exceeds_gain():
    # tiny APY delta + huge gas => gain < cost
    snap = _validated(9.0, 9.05, 7.0)
    snap.gas_estimate = 50.0
    policy = Policy(min_apy_delta=0.01, cooldown_seconds=0, hold_period_days=1)
    decision = AgentDecision(action=Action.REALLOCATE, from_pool="PoolA",
                             to_pool="PoolB", amount=100, confidence=1.0,
                             reasoning_trace="marginal")
    gr = make_guardrails_node(lambda: None)
    out = gr({"validated": snap, "policy": policy, "agent_decision": decision})
    failed = [g for g in out["guardrail_results"] if not g.passed]
    assert failed and failed[0].name == "cost_check"


def test_guardrails_all_pass_for_good_move():
    snap = _validated(7.0, 15.0, 7.0)
    policy = Policy(cooldown_seconds=0, hold_period_days=365)
    decision = deterministic_decision(snap, policy)
    gr = make_guardrails_node(lambda: None)
    out = gr({"validated": snap, "policy": policy, "agent_decision": decision})
    assert all(g.passed for g in out["guardrail_results"])
