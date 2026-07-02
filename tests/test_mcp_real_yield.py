"""Offline unit tests for the real yield derivation (no network)."""
from agent.mcp_real import CsprTradeClient


def _pair(reserve0, decimals0=9):
    return {"token0": {"decimals": decimals0}, "reserve0": str(reserve0)}


def test_fee_apr_from_volume_and_tvl():
    # TVL token0 = 1000 (1e9 base units @ 9dp per unit -> 1000 units means 1000e9)
    pair = _pair(1000 * 10**9)
    # two candles 1 day apart, 300 token0 volume total, fee 0.3%
    history = [
        {"timestamp": "2026-02-18T00:00:00Z", "open": 1.0, "close": 1.0, "volumeToken0": 150},
        {"timestamp": "2026-02-19T00:00:00Z", "open": 1.0, "close": 1.0, "volumeToken0": 150},
    ]
    c = CsprTradeClient.__new__(CsprTradeClient)  # no network init
    apr = CsprTradeClient.fee_apr(c, pair, history)
    # daily fees = 300*0.003 / 1day = 0.9 ; annual = 328.5 ; /1000 tvl = 0.3285 -> 32.85%
    assert 30 < apr < 36


def test_fee_apr_zero_when_no_tvl():
    c = CsprTradeClient.__new__(CsprTradeClient)
    assert CsprTradeClient.fee_apr(c, _pair(0), [{"timestamp": "2026-01-01T00:00:00Z", "volumeToken0": 10}]) == 0.0


def test_price_apr_annualizes_return():
    history = [
        {"timestamp": "2026-02-18T00:00:00Z", "open": 100.0, "close": 100.0},
        {"timestamp": "2026-02-19T00:00:00Z", "open": 101.0, "close": 101.0},
    ]
    apr = CsprTradeClient.price_apr(history)
    # 1% over 1 day annualized = 365%
    assert 360 < apr < 370


def test_history_span_floor():
    # single timestamp -> floor at 1h, no div-by-zero
    h = [{"timestamp": "2026-02-18T00:00:00Z", "open": 1, "close": 1}]
    assert CsprTradeClient._history_span_days(h) >= 1 / 24
