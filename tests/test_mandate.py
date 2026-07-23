"""Plain-English mandate + safety-envelope behavior (Phase 2)."""
from agent.decision import within_safety_envelope
from agent.types import Action, AgentDecision, PoolReading, Policy, ValidatedSnapshot


def _snap(a=7.0, b=13.0, c=9.0, alloc=(400, 400, 200)):
    pools = {
        "PoolA": PoolReading(pool_id="PoolA", apy=a, allocation=alloc[0]),
        "PoolB": PoolReading(pool_id="PoolB", apy=b, allocation=alloc[1]),
        "PoolC": PoolReading(pool_id="PoolC", apy=c, allocation=alloc[2]),
    }
    return ValidatedSnapshot(pools=pools, gas_estimate=0.1,
                             cross_source_apy={k: v.apy for k, v in pools.items()})


def _move(frm, to, amt):
    return AgentDecision(action=Action.REALLOCATE, from_pool=frm, to_pool=to,
                         amount=amt, reasoning_trace="t")


def test_envelope_allows_partial_and_alternative_targets():
    snap, policy = _snap(), Policy(min_apy_delta=1.0)
    # greedy would be PoolA->PoolB full 250; a conservative partial is still safe
    ok, _ = within_safety_envelope(_move("PoolA", "PoolB", 100.0), snap, policy)
    assert ok
    # an alternative up-yield target (diversification mandate) is safe
    ok, _ = within_safety_envelope(_move("PoolA", "PoolC", 50.0), snap, policy)
    assert ok


def test_envelope_blocks_unsafe():
    snap, policy = _snap(), Policy(min_apy_delta=1.0)
    # into a worse-yielding pool
    assert not within_safety_envelope(_move("PoolB", "PoolC", 10.0), snap, policy)[0]
    # over the position cap (25% of 1000 = 250)
    assert not within_safety_envelope(_move("PoolA", "PoolB", 300.0), snap, policy)[0]
    # more than the source holds
    assert not within_safety_envelope(_move("PoolC", "PoolB", 9999.0), snap, policy)[0]
    # edge below threshold
    tight = _snap(a=12.5, b=13.0, c=9.0)
    assert not within_safety_envelope(_move("PoolA", "PoolB", 50.0), tight,
                                      Policy(min_apy_delta=1.0))[0]


def test_hold_always_in_envelope():
    snap = _snap()
    hold = AgentDecision(action=Action.HOLD, reasoning_trace="hold")
    assert within_safety_envelope(hold, snap, Policy())[0]


def test_policy_mandate_roundtrips():
    p = Policy(mandate="stay conservative; keep 20% in PoolC")
    restored = Policy.model_validate_json(p.model_dump_json())
    assert restored.mandate == "stay conservative; keep 20% in PoolC"
    assert Policy().mandate == ""  # default empty = pure yield-max
