"""Cedar LangGraph StateGraph.

Flow:
    OBSERVE -> VALIDATE -> (fail) -> LOG
                        \\-> REASON -> RECHECK -> (HOLD or disagree) -> LOG
                                              \\-> (REALLOCATE + agree) -> GUARDRAILS
                                                    -> (any fail) -> LOG
                                                    -> (all pass)  -> ACTUATE -> LOG
"""
from __future__ import annotations

import time
import uuid

from langgraph.graph import END, StateGraph

from .cspr_click import Signer, get_default_signer
from .mcp_clients import MarketDataSource, get_default_source
from .nodes.actuate import make_actuate_node
from .nodes.guardrails import make_guardrails_node
from .nodes.log import make_log_node
from .nodes.observe import make_observe_node
from .nodes.reason import make_reason_node
from .nodes.recheck import recheck
from .nodes.validate import validate
from .types import Action, CycleState, Outcome, Policy


class CedarAgent:
    """Bundles the compiled graph with its runtime dependencies (data source,
    signer, and the store-backed providers/sinks)."""

    def __init__(self, *, source: MarketDataSource, signer: Signer,
                 allocations_provider, apply_reallocation,
                 last_reallocation_provider, record_cycle,
                 force_deterministic: bool = False):
        self.source = source
        self.signer = signer
        self._record_cycle = record_cycle
        self._apply = apply_reallocation

        observe = make_observe_node(source, allocations_provider)
        reason = make_reason_node(force_deterministic=force_deterministic)
        guardrails = make_guardrails_node(last_reallocation_provider)
        actuate = make_actuate_node(signer, apply_reallocation)
        log = make_log_node(record_cycle)

        g = StateGraph(CycleState)
        g.add_node("observe", observe)
        g.add_node("validate", validate)
        g.add_node("reason", reason)
        g.add_node("recheck", recheck)
        g.add_node("guardrails", guardrails)
        g.add_node("actuate", actuate)
        g.add_node("log", log)

        g.set_entry_point("observe")
        g.add_edge("observe", "validate")
        g.add_conditional_edges("validate", _after_validate,
                                {"reason": "reason", "log": "log"})
        g.add_edge("reason", "recheck")
        g.add_conditional_edges("recheck", _after_recheck,
                                {"guardrails": "guardrails", "log": "log"})
        g.add_conditional_edges("guardrails", _after_guardrails,
                                {"actuate": "actuate", "log": "log"})
        g.add_edge("actuate", "log")
        g.add_edge("log", END)

        self.graph = g.compile()

    def run_cycle(self, policy: Policy) -> CycleState:
        state: CycleState = {
            "cycle_id": uuid.uuid4().hex[:12],
            "policy": policy,
            "started_at": time.time(),
        }
        return self.graph.invoke(state)


# -- routing predicates ------------------------------------------------------
def _after_validate(state: CycleState) -> str:
    return "log" if "validation_failure" in state else "reason"


def _after_recheck(state: CycleState) -> str:
    decision = state["agent_decision"]
    if decision.action != Action.REALLOCATE:
        return "log"
    if not state.get("recheck_agrees", False):
        return "log"
    return "guardrails"


def _after_guardrails(state: CycleState) -> str:
    results = state.get("guardrail_results", [])
    if results and all(g.passed for g in results):
        return "actuate"
    return "log"


def build_default_agent(store, *, force_deterministic: bool = False,
                        source: MarketDataSource | None = None,
                        signer: Signer | None = None,
                        allocations_provider=None) -> CedarAgent:
    """Convenience wiring against a Store instance. Allocations come from the
    chain (VaultRouter dictionary read) when VAULT_ROUTER_HASH is configured,
    falling back to the local cache with a logged warning otherwise."""
    if allocations_provider is None:
        from .chain_state import make_allocations_provider
        allocations_provider = make_allocations_provider(store)
    return CedarAgent(
        source=source or get_default_source(),
        signer=signer or get_default_signer(),
        allocations_provider=allocations_provider,
        apply_reallocation=store.apply_reallocation,
        last_reallocation_provider=store.last_reallocation_time,
        record_cycle=store.record_cycle,
        force_deterministic=force_deterministic,
    )
