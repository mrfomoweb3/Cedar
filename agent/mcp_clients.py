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

            return MarketSnapshot(pools=pools, gas_estimate=self._gas,
                                  cross_source_apy=cross)


# ---------------------------------------------------------------------------
# Real source (documented seam)
# ---------------------------------------------------------------------------
class CasperMCPDataSource:
    """Real adapter over Casper MCP Server + CSPR.trade MCP.

    Fill in ``get_snapshot`` with MCP client calls once the servers are
    configured. Kept API-compatible with the mock so nothing else changes.
    """

    def __init__(self, casper_mcp_url: Optional[str] = None,
                 cspr_trade_mcp_url: Optional[str] = None):
        self.casper_mcp_url = casper_mcp_url or os.getenv("CASPER_MCP_URL", "")
        self.cspr_trade_mcp_url = cspr_trade_mcp_url or os.getenv("CSPR_TRADE_MCP_URL", "")

    def get_snapshot(self, allocations: dict[str, float]) -> MarketSnapshot:  # pragma: no cover
        raise NotImplementedError(
            "Wire Casper MCP + CSPR.trade MCP clients here. Expected: per-pool APY "
            "from both sources (-> pools + cross_source_apy) and a gas estimate."
        )


def get_default_source() -> MarketDataSource:
    """Selects data source from env. Defaults to mock for local/demo."""
    if os.getenv("CEDAR_DATA_SOURCE", "mock").lower() == "casper":
        return CasperMCPDataSource()
    return MockMarketDataSource()
