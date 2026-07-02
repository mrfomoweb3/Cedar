"""Segment 2 test gate: Observe returns real (mock) data; Validate passes good
data and rejects bad/stale data."""
import time

from agent.mcp_clients import MockMarketDataSource
from agent.nodes.validate import validate
from agent.types import MarketSnapshot, Policy, PoolReading


def _snapshot(apy_a=8.0, apy_b=9.0, apy_c=7.0, cross=None, ts=None):
    pools = {
        "PoolA": PoolReading(pool_id="PoolA", apy=apy_a, allocation=400),
        "PoolB": PoolReading(pool_id="PoolB", apy=apy_b, allocation=400),
        "PoolC": PoolReading(pool_id="PoolC", apy=apy_c, allocation=200),
    }
    snap = MarketSnapshot(pools=pools, gas_estimate=0.1,
                          cross_source_apy=cross or {"PoolA": apy_a, "PoolB": apy_b, "PoolC": apy_c})
    if ts is not None:
        snap.timestamp = ts
    return snap


def test_observe_returns_data():
    src = MockMarketDataSource(seed=3)
    snap = src.get_snapshot({"PoolA": 400, "PoolB": 400, "PoolC": 200})
    assert set(snap.pools) == {"PoolA", "PoolB", "PoolC"}
    assert all(0 < r.apy < 50 for r in snap.pools.values())
    assert snap.total_value == 1000


def test_validate_passes_good_data():
    out = validate({"snapshot": _snapshot(), "policy": Policy()})
    assert "validated" in out
    assert "validation_failure" not in out


def test_validate_rejects_absurd_apy():
    # 9000% is bad data, not a jackpot.
    out = validate({"snapshot": _snapshot(apy_b=9000.0,
                                          cross={"PoolA": 8.0, "PoolB": 9000.0, "PoolC": 7.0}),
                    "policy": Policy()})
    assert "validated" not in out
    assert "validation_failure" in out
    assert "out of bounds" in out["validation_failure"].detail


def test_validate_rejects_stale_data():
    stale_ts = time.time() - 10_000
    out = validate({"snapshot": _snapshot(ts=stale_ts), "policy": Policy()})
    assert "validation_failure" in out
    assert "stale" in out["validation_failure"].detail


def test_validate_rejects_cross_source_divergence():
    # casper_mcp says 9%, cspr_trade says 15% -> halt, do not average.
    out = validate({"snapshot": _snapshot(cross={"PoolA": 8.0, "PoolB": 15.0, "PoolC": 7.0}),
                    "policy": Policy()})
    assert "validation_failure" in out
    assert "divergence" in out["validation_failure"].detail
