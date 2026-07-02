"""Persistent store (SQLite): cycle log, policy, allocations, run-state.

One ``cycles`` table is the source of truth for the Dashboard feed and the
Audit Log. Allocations are cached locally so the loop can read current on-chain
state without an extra call each cycle (and so demos work fully offline); the
real VaultRouter get_allocation values would reconcile this in production.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Optional

from agent.types import POOL_IDS, Policy

DB_PATH = os.getenv("CEDAR_DB", os.path.join(os.path.dirname(__file__), "..", "data", "cedar.db"))


class Store:
    def __init__(self, path: str = DB_PATH):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cycles (
                    id            TEXT PRIMARY KEY,
                    started_at    REAL NOT NULL,
                    finished_at   REAL,
                    outcome       TEXT NOT NULL,
                    action        TEXT,
                    from_pool     TEXT,
                    to_pool       TEXT,
                    amount        REAL,
                    confidence    REAL,
                    reasoning     TEXT,
                    recheck_agrees INTEGER,
                    hold_reason   TEXT,
                    tx_hash       TEXT,
                    snapshot_json TEXT,
                    guardrails_json TEXT
                );
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS allocations (
                    pool_id TEXT PRIMARY KEY,
                    amount  REAL NOT NULL
                );
                """
            )
            # seed allocations if empty
            cur = self._conn.execute("SELECT COUNT(*) AS c FROM allocations")
            if cur.fetchone()["c"] == 0:
                seed = {"PoolA": 400.0, "PoolB": 400.0, "PoolC": 200.0}
                for pid in POOL_IDS:
                    self._conn.execute(
                        "INSERT INTO allocations(pool_id, amount) VALUES(?,?)",
                        (pid, seed.get(pid, 0.0)),
                    )

    # -- cycle log ---------------------------------------------------------
    def record_cycle(self, record: dict[str, Any]) -> None:
        cols = ("id", "started_at", "finished_at", "outcome", "action", "from_pool",
                "to_pool", "amount", "confidence", "reasoning", "recheck_agrees",
                "hold_reason", "tx_hash", "snapshot_json", "guardrails_json")
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT OR REPLACE INTO cycles({','.join(cols)}) "
                f"VALUES({','.join('?' for _ in cols)})",
                tuple(record.get(c) for c in cols),
            )

    def feed(self, limit: int = 50, offset: int = 0,
             outcome: Optional[str] = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM cycles"
        params: list[Any] = []
        if outcome:
            q += " WHERE outcome = ?"
            params.append(outcome)
        q += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_cycles(self, outcome: Optional[str] = None) -> int:
        q = "SELECT COUNT(*) AS c FROM cycles"
        params: list[Any] = []
        if outcome:
            q += " WHERE outcome = ?"
            params.append(outcome)
        with self._lock:
            return self._conn.execute(q, params).fetchone()["c"]

    def last_reallocation_time(self) -> Optional[float]:
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(finished_at) AS t FROM cycles WHERE outcome = 'EXECUTED'"
            ).fetchone()
        return row["t"] if row and row["t"] is not None else None

    def guardrail_trigger_counts(self) -> dict[str, int]:
        """Count blocked cycles by the guardrail that blocked them."""
        counts: dict[str, int] = {}
        with self._lock:
            rows = self._conn.execute(
                "SELECT guardrails_json FROM cycles WHERE outcome = 'BLOCKED'"
            ).fetchall()
        for r in rows:
            for g in json.loads(r["guardrails_json"] or "[]"):
                if not g.get("passed", True):
                    counts[g["name"]] = counts.get(g["name"], 0) + 1
        return counts

    @staticmethod
    def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["snapshot"] = json.loads(d.pop("snapshot_json") or "null")
        d["guardrails"] = json.loads(d.pop("guardrails_json") or "[]")
        d["recheck_agrees"] = bool(d.get("recheck_agrees"))
        return d

    # -- allocations -------------------------------------------------------
    def get_allocations(self) -> dict[str, float]:
        with self._lock:
            rows = self._conn.execute("SELECT pool_id, amount FROM allocations").fetchall()
        return {r["pool_id"]: r["amount"] for r in rows}

    def apply_reallocation(self, from_pool: str, to_pool: str, amount: float) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE allocations SET amount = amount - ? WHERE pool_id = ?",
                (amount, from_pool))
            self._conn.execute(
                "UPDATE allocations SET amount = amount + ? WHERE pool_id = ?",
                (amount, to_pool))

    # -- policy & run-state (kv) ------------------------------------------
    def get_policy(self) -> Policy:
        raw = self._kv_get("policy")
        return Policy.model_validate_json(raw) if raw else Policy()

    def set_policy(self, policy: Policy) -> None:
        self._kv_set("policy", policy.model_dump_json())

    def is_paused(self) -> bool:
        return self._kv_get("paused") == "1"

    def set_paused(self, paused: bool) -> None:
        self._kv_set("paused", "1" if paused else "0")

    def get_status(self) -> str:
        return self._kv_get("status") or "idle"

    def set_status(self, status: str) -> None:
        self._kv_set("status", status)

    def get_next_cycle_at(self) -> Optional[float]:
        raw = self._kv_get("next_cycle_at")
        return float(raw) if raw else None

    def set_next_cycle_at(self, ts: float) -> None:
        self._kv_set("next_cycle_at", str(ts))

    def _kv_get(self, key: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def _kv_set(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO kv(key, value) VALUES(?, ?)", (key, value))


_default: Optional[Store] = None


def get_store() -> Store:
    global _default
    if _default is None:
        _default = Store()
    return _default
