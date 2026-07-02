"""Loop scheduler: runs the LangGraph cycle on a fixed interval.

Respects the pause/resume kill switch (checked at the top of each cycle before
OBSERVE). Runs on a background thread so FastAPI can serve while it ticks.
"""
from __future__ import annotations

import logging
import threading
import time

from api.store import Store

from .graph import CedarAgent

log = logging.getLogger("cedar.scheduler")


class Scheduler:
    def __init__(self, agent: CedarAgent, store: Store, interval_seconds: float = 120.0):
        self.agent = agent
        self.store = store
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="cedar-scheduler",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def run_once(self) -> None:
        """Run a single cycle now (used by tests and the /demo triggers)."""
        self.store.set_status("observing")
        policy = self.store.get_policy()
        try:
            state = self.agent.run_cycle(policy)
            self.store.set_status("idle")
            return state
        except Exception:  # noqa: BLE001
            self.store.set_status("error")
            raise

    def _run(self) -> None:
        while not self._stop.is_set():
            # Kill switch: check pause at the top of each cycle.
            try:
                if self.store.is_paused():
                    self.store.set_status("paused")
                else:
                    self.run_once()
            except Exception:  # noqa: BLE001
                # A 24/7 loop must survive a bad cycle (RPC hiccup, MCP timeout,
                # LLM error). Log via status and continue to the next interval.
                log.exception("cycle failed; continuing to next interval")
                try:
                    self.store.set_status("error")
                except Exception:  # noqa: BLE001
                    pass
            try:
                self.store.set_next_cycle_at(time.time() + self.interval)
            except Exception:  # noqa: BLE001
                pass
            # Sleep in small slices so stop()/pause take effect promptly.
            waited = 0.0
            while waited < self.interval and not self._stop.is_set():
                time.sleep(min(1.0, self.interval - waited))
                waited += 1.0
