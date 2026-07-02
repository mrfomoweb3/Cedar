"""Data-provenance surfacing: single-source cycles are flagged, not silent."""
from agent.mcp_clients import MockMarketDataSource
from agent.nodes.reason import make_reason_node
from agent.types import MarketSnapshot, Policy, PoolReading, ValidatedSnapshot


def _validated(verified):
    pools = {"PoolA": PoolReading(pool_id="PoolA", apy=1.0, allocation=500),
             "PoolB": PoolReading(pool_id="PoolB", apy=9.0, allocation=100),
             "PoolC": PoolReading(pool_id="PoolC", apy=7.0, allocation=100)}
    return ValidatedSnapshot(pools=pools, gas_estimate=0.1,
                             cross_source_verified=verified)


def test_provenance_note_single_source():
    snap = _validated({"PoolA": False, "PoolB": False, "PoolC": False})
    assert not snap.fully_cross_verified
    assert "single-source, UNVERIFIED" in snap.provenance_note()


def test_provenance_note_verified():
    snap = _validated({"PoolA": True, "PoolB": True, "PoolC": True})
    assert snap.fully_cross_verified
    assert "VERIFIED" in snap.provenance_note()


def test_reason_prepends_provenance_to_trace():
    snap = _validated({"PoolA": False, "PoolB": False, "PoolC": False})
    reason = make_reason_node(force_deterministic=True)
    out = reason({"validated": snap, "policy": Policy(min_apy_delta=1.0)})
    assert out["agent_decision"].reasoning_trace.startswith("[DATA: single-source, UNVERIFIED")


def test_mock_source_marks_verified():
    # the mock provides a genuine independent second APY reading -> verified
    snap = MockMarketDataSource(seed=1).get_snapshot({"PoolA": 100, "PoolB": 100, "PoolC": 100})
    assert snap.cross_source_verified == {"PoolA": True, "PoolB": True, "PoolC": True}
    assert snap.fully_cross_verified
