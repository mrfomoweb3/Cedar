"""Credit-saving LLM gate: Claude is only called when a reallocation is on the
table; clear HOLD cycles skip the API call entirely."""
import pytest

import agent.nodes.reason as reason_mod
from agent.nodes.reason import make_reason_node
from agent.types import Action, AgentDecision, Policy, PoolReading, ValidatedSnapshot


def _validated(apy_a, apy_b, apy_c):
    pools = {
        "PoolA": PoolReading(pool_id="PoolA", apy=apy_a, allocation=400),
        "PoolB": PoolReading(pool_id="PoolB", apy=apy_b, allocation=400),
        "PoolC": PoolReading(pool_id="PoolC", apy=apy_c, allocation=200),
    }
    return ValidatedSnapshot(pools=pools, gas_estimate=0.1)


def test_gate_skips_llm_on_clear_hold(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(reason_mod, "LLM_GATE", True)

    def boom(*a, **k):
        raise AssertionError("LLM must not be called on a clear HOLD")
    monkeypatch.setattr(reason_mod, "_call_llm", boom)

    # all APYs within 0.3pp, threshold 1.0 -> nothing actionable
    out = make_reason_node()( {"validated": _validated(8.0, 8.2, 8.1),
                               "policy": Policy(min_apy_delta=1.0)})
    d = out["agent_decision"]
    assert d.action == Action.HOLD
    assert "skipped" in d.reasoning_trace


def test_gate_calls_llm_when_actionable(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(reason_mod, "LLM_GATE", True)
    called = {}

    def fake_llm(snap, policy):
        called["yes"] = True
        return AgentDecision(action=Action.HOLD, confidence=0.9,
                             reasoning_trace="model says hold anyway")
    monkeypatch.setattr(reason_mod, "_call_llm", fake_llm)

    out = make_reason_node()({"validated": _validated(7.0, 12.0, 7.0),
                              "policy": Policy(min_apy_delta=1.0)})
    assert called.get("yes") is True
    assert out["agent_decision"].action == Action.HOLD
