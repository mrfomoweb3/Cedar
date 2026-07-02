"""OBSERVE node: pull current market + on-chain state into a MarketSnapshot."""
from __future__ import annotations

from ..mcp_clients import MarketDataSource
from ..types import CycleState


def make_observe_node(source: MarketDataSource, allocations_provider):
    """``allocations_provider`` -> dict[pool_id, amount] (current on-chain state)."""

    def observe(state: CycleState) -> CycleState:
        allocations = allocations_provider()
        snapshot = source.get_snapshot(allocations)
        return {"snapshot": snapshot}

    return observe
