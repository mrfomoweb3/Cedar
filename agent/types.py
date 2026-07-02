"""Typed state objects shared across the Cedar LangGraph agent.

Every node reads/writes the ``CycleState`` TypedDict. The nested Pydantic models
give us validation-on-construction and clean JSON serialization for the log store
and the API layer.
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pools
# ---------------------------------------------------------------------------
# Fixed, pre-vetted pool set (matches the Odra contract's PoolId enum).
POOL_IDS = ("PoolA", "PoolB", "PoolC")
PoolId = Literal["PoolA", "PoolB", "PoolC"]


class Action(str, Enum):
    HOLD = "HOLD"
    REALLOCATE = "REALLOCATE"


class Outcome(str, Enum):
    HOLD = "HOLD"                    # agent decided to hold
    BLOCKED = "BLOCKED"             # a guardrail/recheck blocked a reallocation
    EXECUTED = "EXECUTED"          # reallocation actuated on-chain
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
class PoolReading(BaseModel):
    pool_id: PoolId
    apy: float = Field(description="Annualized yield as a percentage, e.g. 12.5 == 12.5%")
    allocation: float = Field(description="Current on-chain allocation in CSPR (motes/1e9)")
    source: str = Field(default="casper_mcp")


class MarketSnapshot(BaseModel):
    """Raw output of the OBSERVE node before validation."""
    pools: dict[str, PoolReading]
    gas_estimate: float = Field(description="Estimated gas cost of a reallocate tx, in CSPR")
    # Optional second-source APY readings for cross-source consistency checks.
    cross_source_apy: dict[str, float] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    @property
    def total_value(self) -> float:
        return sum(p.allocation for p in self.pools.values())


class ValidatedSnapshot(MarketSnapshot):
    """A MarketSnapshot that has passed every VALIDATE check. Same shape;
    the distinct type is a guarantee that validation ran and succeeded."""
    validated_at: float = Field(default_factory=time.time)


class ValidationFailure(BaseModel):
    reason: str
    detail: str = ""
    timestamp: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
class Policy(BaseModel):
    """The active operating policy. Set at onboarding, editable via Settings."""
    min_apy_delta: float = Field(
        default=1.0,
        description="Minimum APY spread (pct points) between current best-held pool "
        "and a target pool before reallocation is considered.",
    )
    max_reallocation_pct: float = Field(
        default=25.0,
        description="Max percent of total value that may move in a single cycle.",
    )
    cooldown_seconds: float = Field(
        default=300.0,
        description="Minimum time between two reallocations.",
    )
    allowed_pools: list[str] = Field(default_factory=lambda: list(POOL_IDS))
    # Validation bounds
    apy_min_bound: float = 0.0
    apy_max_bound: float = 50.0
    freshness_seconds: float = 120.0
    cross_source_tolerance: float = 1.0  # pct points
    # Cost model
    expected_slippage_pct: float = 0.1
    hold_period_days: float = 30.0  # horizon used to weigh gas vs apy gain


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------
class AgentDecision(BaseModel):
    """Schema the reasoning LLM must emit; also used for the deterministic recheck."""
    action: Action
    from_pool: Optional[str] = None
    to_pool: Optional[str] = None
    amount: Optional[float] = None
    confidence: float = 0.0
    reasoning_trace: str = ""


class GuardrailResult(BaseModel):
    name: str
    passed: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------
class CycleState(TypedDict, total=False):
    """The typed state threaded through the StateGraph for a single cycle."""
    cycle_id: str
    policy: Policy
    snapshot: MarketSnapshot
    validated: ValidatedSnapshot
    validation_failure: ValidationFailure
    agent_decision: AgentDecision
    recheck_decision: AgentDecision
    recheck_agrees: bool
    guardrail_results: list[GuardrailResult]
    outcome: Outcome
    tx_hash: Optional[str]
    hold_reason: str
    started_at: float
    finished_at: float
