"""Segment 3 test gate: HOLD below threshold, REALLOCATE above, and code-side
force-rejection of a malformed LLM response (pool not in snapshot, fabricated
figure, over-cap amount)."""
from agent.nodes.reason import _sanitize, make_reason_node
from agent.types import (Action, AgentDecision, Policy, ValidatedSnapshot,
                         PoolReading)


def _validated(apy_a=8.0, apy_b=9.0, apy_c=7.0):
    pools = {
        "PoolA": PoolReading(pool_id="PoolA", apy=apy_a, allocation=400),
        "PoolB": PoolReading(pool_id="PoolB", apy=apy_b, allocation=400),
        "PoolC": PoolReading(pool_id="PoolC", apy=apy_c, allocation=200),
    }
    return ValidatedSnapshot(pools=pools, gas_estimate=0.1,
                             cross_source_apy={k: v.apy for k, v in pools.items()})


def test_hold_when_delta_below_threshold():
    # all APYs within ~0.5pp of each other, threshold 1.0
    snap = _validated(8.0, 8.3, 8.1)
    reason = make_reason_node(force_deterministic=True)
    out = reason({"validated": snap, "policy": Policy(min_apy_delta=1.0)})
    assert out["agent_decision"].action == Action.HOLD


def test_reallocate_when_delta_clears_threshold():
    snap = _validated(7.0, 12.0, 7.0)  # PoolB clearly best
    reason = make_reason_node(force_deterministic=True)
    out = reason({"validated": snap, "policy": Policy(min_apy_delta=1.0)})
    d = out["agent_decision"]
    assert d.action == Action.REALLOCATE
    assert d.to_pool == "PoolB"


def test_sanitize_rejects_unknown_pool():
    snap = _validated()
    bad = AgentDecision(action=Action.REALLOCATE, from_pool="PoolA",
                        to_pool="PoolZ", amount=50, confidence=0.9,
                        reasoning_trace="move to PoolZ")
    out = _sanitize(bad, snap, Policy())
    assert out.action == Action.HOLD
    assert "not in the validated snapshot" in out.reasoning_trace


def test_sanitize_rejects_over_cap_amount():
    snap = _validated()  # total 1000, cap 25% -> 250
    bad = AgentDecision(action=Action.REALLOCATE, from_pool="PoolA",
                        to_pool="PoolB", amount=900, confidence=0.9,
                        reasoning_trace="move 900")
    out = _sanitize(bad, snap, Policy(max_reallocation_pct=25.0))
    assert out.action == Action.HOLD
    assert "exceeds max" in out.reasoning_trace


def test_sanitize_rejects_fabricated_figure():
    snap = _validated(8.0, 9.0, 7.0)  # no 42.7 anywhere
    bad = AgentDecision(action=Action.REALLOCATE, from_pool="PoolA",
                        to_pool="PoolB", amount=100, confidence=0.9,
                        reasoning_trace="PoolB APY is 42.7% which is great")
    out = _sanitize(bad, snap, Policy())
    assert out.action == Action.HOLD
    assert "not present in the snapshot" in out.reasoning_trace


def test_sanitize_allows_derived_arithmetic():
    # Regression: a trace citing a legitimately-derived non-% figure (annual gain
    # = apy-delta * amount) must NOT be force-held as "fabricated".
    snap = _validated(0.438, 1.072, 9.182)
    d = AgentDecision(action=Action.REALLOCATE, from_pool="PoolA", to_pool="PoolC",
                      amount=100, confidence=0.95,
                      reasoning_trace=("Delta PoolA 0.438% to PoolC 9.182% is 8.744%; "
                                       "annual gain ~8.744% * 250 = ~21.86 units vs gas 0.5"))
    out = _sanitize(d, snap, Policy(min_apy_delta=1.0))
    assert out.action == Action.REALLOCATE  # 21.86 / 250 are derived, not fabricated


def test_sanitize_accepts_valid_reallocation():
    snap = _validated(7.0, 12.0, 7.0)
    good = AgentDecision(action=Action.REALLOCATE, from_pool="PoolA",
                         to_pool="PoolB", amount=200, confidence=0.8,
                         reasoning_trace="Move from PoolA 7.0% to PoolB 12.0%, delta 5.0")
    out = _sanitize(good, snap, Policy())
    assert out.action == Action.REALLOCATE
