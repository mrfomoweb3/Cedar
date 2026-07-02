"""Segment 5 test gate: full end-to-end cycles produce correct outcomes and log
records. Reallocation path (spike) => EXECUTED + tx hash. Guardrail-triggering
path (cooldown) => BLOCKED, no tx. Log captures both with full detail."""
from agent.types import Outcome, Policy


def test_e2e_spike_triggers_execution(store, source, signer):
    from agent.graph import build_default_agent
    agent = build_default_agent(store, force_deterministic=True,
                                source=source, signer=signer)
    policy = Policy(cooldown_seconds=0, hold_period_days=365, min_apy_delta=1.0)
    source.spike("PoolB", 20.0)
    state = agent.run_cycle(policy)
    assert state["outcome"] == Outcome.EXECUTED
    assert state["tx_hash"] and len(state["tx_hash"]) == 64
    # allocation moved
    allocs = store.get_allocations()
    assert allocs["PoolB"] > 400


def test_e2e_cooldown_blocks_second_cycle(store, source, signer):
    from agent.graph import build_default_agent
    agent = build_default_agent(store, force_deterministic=True,
                                source=source, signer=signer)
    policy = Policy(cooldown_seconds=9999, hold_period_days=365, min_apy_delta=1.0)
    source.spike("PoolB", 20.0)
    first = agent.run_cycle(policy)
    assert first["outcome"] == Outcome.EXECUTED
    source.spike("PoolB", 22.0)
    second = agent.run_cycle(policy)
    assert second["outcome"] == Outcome.BLOCKED
    assert second.get("tx_hash") is None
    assert "cooldown" in second["hold_reason"]


def test_e2e_validation_failure_logs_hold(store, source, signer):
    from agent.graph import build_default_agent
    agent = build_default_agent(store, force_deterministic=True,
                                source=source, signer=signer)
    policy = Policy()
    source.inject_bad_reading("PoolA", 9000.0)
    state = agent.run_cycle(policy)
    assert state["outcome"] == Outcome.VALIDATION_FAILED
    assert state.get("tx_hash") is None


def test_log_captures_both_outcomes(store, source, signer):
    from agent.graph import build_default_agent
    agent = build_default_agent(store, force_deterministic=True,
                                source=source, signer=signer)
    policy = Policy(cooldown_seconds=9999, hold_period_days=365, min_apy_delta=1.0)
    source.spike("PoolB", 20.0)
    agent.run_cycle(policy)          # EXECUTED
    source.spike("PoolB", 25.0)
    agent.run_cycle(policy)          # BLOCKED (cooldown)

    feed = store.feed(limit=10)
    outcomes = {row["outcome"] for row in feed}
    assert "EXECUTED" in outcomes
    assert "BLOCKED" in outcomes
    executed = next(r for r in feed if r["outcome"] == "EXECUTED")
    assert executed["tx_hash"]
    assert executed["snapshot"] is not None
    assert executed["reasoning"]


def test_execution_failure_surfaced(store, source, signer):
    from agent.graph import build_default_agent
    agent = build_default_agent(store, force_deterministic=True,
                                source=source, signer=signer)
    policy = Policy(cooldown_seconds=0, hold_period_days=365, min_apy_delta=1.0)
    source.spike("PoolB", 20.0)
    signer.fail_next()
    state = agent.run_cycle(policy)
    assert state["outcome"] == Outcome.EXECUTION_FAILED
    assert state.get("tx_hash") is None
