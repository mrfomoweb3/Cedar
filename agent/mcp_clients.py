"""Chain-read adapters: Casper MCP Server + CSPR.trade MCP.

Design: a thin ``MarketDataSource`` protocol with two concrete implementations:

  * ``MockMarketDataSource`` -- deterministic, seedable, drives local dev/tests
    and the demo scenarios. Reads live now; no external server required.
  * ``CasperMCPDataSource`` -- real MCP client. Left as a documented seam; wire
    the Casper MCP + CSPR.trade MCP endpoints in when creds/servers are present.

The graph depends only on the protocol, so swapping mock->real is a one-line
change in ``scheduler.py`` / app startup.
"""
from __future__ import annotations

import os
import random
import threading
from typing import Optional, Protocol

from .types import POOL_IDS, MarketSnapshot, PoolReading


class MarketDataSource(Protocol):
    def get_snapshot(self, allocations: dict[str, float]) -> MarketSnapshot:
        """Return a fresh MarketSnapshot. ``allocations`` is the current on-chain
        allocation per pool (read from the VaultRouter contract by the caller),
        so the data source only has to supply market-side numbers (APY, gas)."""
        ...


# ---------------------------------------------------------------------------
# Mock source
# ---------------------------------------------------------------------------
class MockMarketDataSource:
    """Deterministic, mutable APY simulator.

    APYs random-walk within sane bounds each tick. Demo scenarios can pin or
    spike a pool via ``set_apy`` / ``spike`` and inject bad data via
    ``inject_bad_reading`` to exercise the validation guardrail on camera.
    """

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self._apy: dict[str, float] = {
            "PoolA": 8.0,
            "PoolB": 9.5,
            "PoolC": 7.0,
        }
        self._gas = 0.12
        self._bad_reading: Optional[tuple[str, float]] = None
        self._cross_divergence: Optional[tuple[str, float]] = None

    # -- controls used by demo seeding -------------------------------------
    def set_apy(self, pool_id: str, apy: float) -> None:
        with self._lock:
            self._apy[pool_id] = apy

    def spike(self, pool_id: str, apy: float) -> None:
        """Seed a controlled APY spike (demo scenario 1)."""
        self.set_apy(pool_id, apy)

    def inject_bad_reading(self, pool_id: str, apy: float) -> None:
        """Force an out-of-bounds APY on the next snapshot (validation demo)."""
        with self._lock:
            self._bad_reading = (pool_id, apy)

    def inject_cross_divergence(self, pool_id: str, second_source_apy: float) -> None:
        """Make CSPR.trade disagree with Casper MCP for one pool."""
        with self._lock:
            self._cross_divergence = (pool_id, second_source_apy)

    # -- read --------------------------------------------------------------
    def get_snapshot(self, allocations: dict[str, float]) -> MarketSnapshot:
        with self._lock:
            # gentle random walk so successive cycles differ
            for pid in POOL_IDS:
                drift = self._rng.uniform(-0.3, 0.3)
                self._apy[pid] = round(max(0.5, self._apy[pid] + drift), 3)

            pools: dict[str, PoolReading] = {}
            cross: dict[str, float] = {}
            for pid in POOL_IDS:
                apy = self._apy[pid]
                pools[pid] = PoolReading(
                    pool_id=pid,
                    apy=apy,
                    allocation=float(allocations.get(pid, 0.0)),
                    source="casper_mcp",
                )
                # second source normally agrees within a hair
                cross[pid] = round(apy + self._rng.uniform(-0.05, 0.05), 3)

            if self._bad_reading is not None:
                pid, bad = self._bad_reading
                pools[pid] = PoolReading(pool_id=pid, apy=bad,
                                         allocation=float(allocations.get(pid, 0.0)))
                self._bad_reading = None

            if self._cross_divergence is not None:
                pid, val = self._cross_divergence
                cross[pid] = val
                self._cross_divergence = None

            # Mock provides a genuine independent second APY reading per pool.
            verified = {pid: True for pid in POOL_IDS}
            return MarketSnapshot(pools=pools, gas_estimate=self._gas,
                                  cross_source_apy=cross,
                                  cross_source_verified=verified)


# ---------------------------------------------------------------------------
# Real source (documented seam)
# ---------------------------------------------------------------------------
class CasperMCPDataSource:
    """Real adapter over CSPR.trade MCP (+ optional Casper MCP second source).

    OBSERVE maps the three highest-TVL, actively-traded DEX pools to
    PoolA/PoolB/PoolC (a stable mapping resolved once per process) and reports
    each pool's real fee-APR yield. The cross-source APY comes from the Casper
    MCP server when a cspr.cloud key is configured; otherwise it mirrors the
    primary reading and the two-provider divergence check is a documented no-op
    until that key is supplied.

    ``allocations`` (current on-chain positions) is passed through from the
    caller and kept in sync with the contract by the signer, so the derived
    snapshot matches on-chain state and reallocations won't revert.
    """

    MIN_CANDLES = 12  # require real trading history so fee APR isn't a 1-swap spike

    def __init__(self, cspr_trade_mcp_url: Optional[str] = None):
        from .mcp_real import CasperCloudClient, CsprTradeClient, MCPError

        self._MCPError = MCPError
        self._trade = CsprTradeClient(cspr_trade_mcp_url)
        # Gas estimate for the cost-check guardrail: the actual payment the
        # signer attaches to a reallocate deploy (Casper fixed-price charges the
        # full payment), overridable via CASPER_GAS_ESTIMATE.
        payment_cspr = float(os.getenv("CASPER_CALL_PAYMENT", "5000000000")) / 1e9
        self._gas_estimate = float(os.getenv("CASPER_GAS_ESTIMATE", str(payment_cspr)))
        self._mapping: Optional[dict[str, str]] = None  # PoolA/B/C -> pair hash
        # Optional real second source (Casper MCP); disabled if no key present.
        self._casper: Optional[object] = None
        if os.getenv("CSPR_CLOUD_API_KEY"):  # URL auto-defaults per network
            try:
                self._casper = CasperCloudClient()
            except MCPError:
                self._casper = None

    def _resolve_mapping(self) -> dict[str, str]:
        """Pick the 3 highest-TVL pools with real history; cache for stability."""
        if self._mapping is not None:
            return self._mapping
        pairs = self._trade.get_pairs()
        scored = []
        for p in pairs:
            try:
                hist = self._trade.get_pair_price_history(p["contractPackageHash"])
            except Exception:
                continue
            if len(hist) >= self.MIN_CANDLES:
                scored.append((self._trade._tvl_token0(p), p, hist))
        scored.sort(key=lambda r: r[0], reverse=True)
        top = scored[:3]
        if len(top) < 3:
            raise self._MCPError(
                f"only {len(top)} pools with >= {self.MIN_CANDLES} candles; "
                "cannot map PoolA/B/C to real pools")
        self._mapping = {pid: top[i][1]["contractPackageHash"]
                         for i, pid in enumerate(POOL_IDS)}
        self._labels = {pid: f"{top[i][1]['token0']['symbol']}/{top[i][1]['token1']['symbol']}"
                        for i, pid in enumerate(POOL_IDS)}
        return self._mapping

    def get_snapshot(self, allocations: dict[str, float]) -> MarketSnapshot:
        mapping = self._resolve_mapping()
        pairs = {p["contractPackageHash"]: p for p in self._trade.get_pairs()}
        pools: dict[str, PoolReading] = {}
        cross: dict[str, float] = {}
        implied_price: dict[str, float] = {}
        cross_price: dict[str, float] = {}
        for pid in POOL_IDS:
            pair = pairs[mapping[pid]]
            hist = self._trade.get_pair_price_history(mapping[pid])
            apy = round(self._trade.fee_apr(pair, hist), 3)
            pools[pid] = PoolReading(pool_id=pid, apy=apy,
                                     allocation=float(allocations.get(pid, 0.0)),
                                     source="cspr_trade")
            cross[pid] = apy  # no second APY provider; APY divergence is a no-op

            # Real two-provider PRICE cross-check (CSPR.trade reserves vs cspr.cloud).
            price = self._implied_price(pair)
            if price is not None:
                implied_price[pid] = price
                second = self._casper_price(pair) if self._casper else None
                if second is not None:
                    cross_price[pid] = second
        # A pool is cross-verified only when a real 2nd-provider price came back.
        verified = {pid: pid in cross_price for pid in POOL_IDS}
        return MarketSnapshot(pools=pools, gas_estimate=self._gas_estimate,
                              cross_source_apy=cross, implied_price=implied_price,
                              cross_source_price=cross_price,
                              cross_source_verified=verified)

    @staticmethod
    def _implied_price(pair: dict) -> Optional[float]:
        """token0->token1 price implied by CSPR.trade reserves, decimal-adjusted."""
        try:
            d0 = pair["token0"].get("decimals", 9)
            d1 = pair["token1"].get("decimals", 9)
            r0 = int(pair["reserve0"]) / (10 ** d0)
            r1 = int(pair["reserve1"]) / (10 ** d1)
            return r1 / r0 if r0 > 0 else None
        except Exception:
            return None

    def _casper_price(self, pair: dict) -> Optional[float]:
        """Independent cspr.cloud DEX rate for the pool's token pair, if indexed.
        Returns None when cspr.cloud has no rate for these tokens (the case for
        CSPR.trade's low-activity testnet test-tokens) -> price check skips."""
        try:
            return self._casper.dex_rate(pair["token0"]["packageHash"],
                                         pair["token1"]["packageHash"])
        except Exception:
            return None


def get_default_source() -> MarketDataSource:
    """Selects data source from env. Defaults to mock for local/demo."""
    if os.getenv("CEDAR_DATA_SOURCE", "mock").lower() == "casper":
        return CasperMCPDataSource()
    return MockMarketDataSource()
