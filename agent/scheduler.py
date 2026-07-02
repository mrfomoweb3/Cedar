"""Loop scheduler: runs the LangGraph cycle on a fixed interval.

Respects the pause/resume kill switch (checked at the top of each cycle before
OBSERVE). Runs on a background thread so FastAPI can serve while it ticks.
"""
from __future__ import annotations

import threading
import time

from api.store import Store

from .graph import CedarAgent


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
            if self.store.is_paused():
                self.store.set_status("paused")
            else:
                self.run_once()
            self.store.set_next_cycle_at(time.time() + self.interval)
            # Sleep in small slices so stop()/pause take effect promptly.
            waited = 0.0
            while waited < self.interval and not self._stop.is_set():
                time.sleep(min(1.0, self.interval - waited))
                waited += 1.0
