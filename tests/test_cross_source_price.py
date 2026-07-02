"""Two-provider price cross-check in VALIDATE (offline)."""
from agent.nodes.validate import validate
from agent.types import MarketSnapshot, Policy, PoolReading


def _snap(implied, cross):
    pools = {"PoolA": PoolReading(pool_id="PoolA", apy=5.0, allocation=100),
             "PoolB": PoolReading(pool_id="PoolB", apy=6.0, allocation=100),
             "PoolC": PoolReading(pool_id="PoolC", apy=7.0, allocation=100)}
    return MarketSnapshot(pools=pools, gas_estimate=0.1,
                          cross_source_apy={k: v.apy for k, v in pools.items()},
                          implied_price=implied, cross_source_price=cross)


def test_price_agreement_passes():
    out = validate({"snapshot": _snap({"PoolA": 1.000}, {"PoolA": 1.004}),
                    "policy": Policy(cross_source_tolerance=1.0)})
    assert "validated" in out  # 0.4% < 1% tolerance


def test_price_divergence_halts():
    out = validate({"snapshot": _snap({"PoolA": 1.000}, {"PoolA": 1.050}),
                    "policy": Policy(cross_source_tolerance=1.0)})
    assert "validation_failure" in out  # 5% > 1%
    assert "PRICE divergence" in out["validation_failure"].detail


def test_missing_cross_price_skips():
    # cspr.cloud had no rate -> pool absent from cross_source_price -> check skipped
    out = validate({"snapshot": _snap({"PoolA": 1.0}, {}), "policy": Policy()})
    assert "validated" in out
