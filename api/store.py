"""Persistent store: cycle log, policy, allocations, run-state.

Backend-agnostic via SQLAlchemy Core:
  * ``DATABASE_URL`` set  -> that database (Postgres in cloud/production)
  * otherwise             -> local SQLite file at ``CEDAR_DB``

The identical code path runs on both, so the production (Postgres) behaviour is
exercised by the SQLite test-suite. One ``cycles`` table is the source of truth
for the Dashboard feed and the Audit Log.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Optional

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, Text,
                        create_engine, delete, func, insert, select, update)
from sqlalchemy.engine import Engine

from agent.types import POOL_IDS, Policy

DB_PATH = os.getenv("CEDAR_DB", os.path.join(os.path.dirname(__file__), "..", "data", "cedar.db"))

_metadata = MetaData()

cycles_t = Table(
    "cycles", _metadata,
    Column("id", String, primary_key=True),
    Column("started_at", Float, nullable=False),
    Column("finished_at", Float),
    Column("outcome", String, nullable=False),
    Column("action", String),
    Column("from_pool", String),
    Column("to_pool", String),
    Column("amount", Float),
    Column("confidence", Float),
    Column("reasoning", Text),
    Column("recheck_agrees", Integer),
    Column("hold_reason", Text),
    Column("tx_hash", String),
    Column("snapshot_json", Text),
    Column("guardrails_json", Text),
)
kv_t = Table(
    "kv", _metadata,
    Column("key", String, primary_key=True),
    Column("value", Text, nullable=False),
)
allocations_t = Table(
    "allocations", _metadata,
    Column("pool_id", String, primary_key=True),
    Column("amount", Float, nullable=False),
)


def _make_engine(url_or_path: str) -> Engine:
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        # normalize common Heroku/Render style prefixes to a psycopg3 driver
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return create_engine(db_url, pool_pre_ping=True, pool_recycle=1800)
    path = os.path.abspath(url_or_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return create_engine(f"sqlite:///{path}",
                         connect_args={"check_same_thread": False})


class Store:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._engine = _make_engine(path)
        self._dialect = self._engine.dialect.name
        _metadata.create_all(self._engine)
        self._seed_allocations()

    # -- upsert helper -----------------------------------------------------
    def _upsert(self, conn, table: Table, values: dict, index_elements: list[str]):
        if self._dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(table).values(**values)
            update_cols = {c: stmt.excluded[c] for c in values if c not in index_elements}
            stmt = stmt.on_conflict_do_update(index_elements=index_elements,
                                              set_=update_cols) if update_cols \
                else stmt.on_conflict_do_nothing(index_elements=index_elements)
        else:  # sqlite
            from sqlalchemy.dialects.sqlite import insert as sq_insert
            stmt = sq_insert(table).values(**values)
            update_cols = {c: stmt.excluded[c] for c in values if c not in index_elements}
            stmt = stmt.on_conflict_do_update(index_elements=index_elements,
                                              set_=update_cols) if update_cols \
                else stmt.on_conflict_do_nothing(index_elements=index_elements)
        conn.execute(stmt)

    def _seed_allocations(self) -> None:
        with self._lock, self._engine.begin() as conn:
            count = conn.execute(select(func.count()).select_from(allocations_t)).scalar()
            if not count:
                seed = {"PoolA": 400.0, "PoolB": 400.0, "PoolC": 200.0}
                for pid in POOL_IDS:
                    conn.execute(insert(allocations_t).values(
                        pool_id=pid, amount=seed.get(pid, 0.0)))

    # -- cycle log ---------------------------------------------------------
    def record_cycle(self, record: dict[str, Any]) -> None:
        cols = ("id", "started_at", "finished_at", "outcome", "action", "from_pool",
                "to_pool", "amount", "confidence", "reasoning", "recheck_agrees",
                "hold_reason", "tx_hash", "snapshot_json", "guardrails_json")
        values = {c: record.get(c) for c in cols}
        with self._lock, self._engine.begin() as conn:
            self._upsert(conn, cycles_t, values, ["id"])

    def feed(self, limit: int = 50, offset: int = 0,
             outcome: Optional[str] = None) -> list[dict[str, Any]]:
        stmt = select(cycles_t)
        if outcome:
            stmt = stmt.where(cycles_t.c.outcome == outcome)
        stmt = stmt.order_by(cycles_t.c.started_at.desc()).limit(limit).offset(offset)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [self._row_to_dict(r) for r in rows]

    def count_cycles(self, outcome: Optional[str] = None) -> int:
        stmt = select(func.count()).select_from(cycles_t)
        if outcome:
            stmt = stmt.where(cycles_t.c.outcome == outcome)
        with self._engine.connect() as conn:
            return int(conn.execute(stmt).scalar() or 0)

    def last_reallocation_time(self) -> Optional[float]:
        stmt = select(func.max(cycles_t.c.finished_at)).where(
            cycles_t.c.outcome == "EXECUTED")
        with self._engine.connect() as conn:
            val = conn.execute(stmt).scalar()
        return float(val) if val is not None else None

    def guardrail_trigger_counts(self) -> dict[str, int]:
        stmt = select(cycles_t.c.guardrails_json).where(cycles_t.c.outcome == "BLOCKED")
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()
        counts: dict[str, int] = {}
        for (gj,) in rows:
            for g in json.loads(gj or "[]"):
                if not g.get("passed", True):
                    counts[g["name"]] = counts.get(g["name"], 0) + 1
        return counts

    @staticmethod
    def _row_to_dict(r) -> dict[str, Any]:
        from agent.cspr_click import redact_secrets
        d = dict(r)
        d["snapshot"] = json.loads(d.pop("snapshot_json") or "null")
        d["guardrails"] = json.loads(d.pop("guardrails_json") or "[]")
        d["recheck_agrees"] = bool(d.get("recheck_agrees"))
        # Never serve key material even if a tool echoed it into a stored field.
        d["hold_reason"] = redact_secrets(d.get("hold_reason"))
        d["reasoning"] = redact_secrets(d.get("reasoning"))
        return d

    # -- allocations -------------------------------------------------------
    def get_allocations(self) -> dict[str, float]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(allocations_t.c.pool_id,
                                       allocations_t.c.amount)).all()
        return {pid: amt for pid, amt in rows}

    def set_allocation(self, pool_id: str, amount: float) -> None:
        with self._lock, self._engine.begin() as conn:
            self._upsert(conn, allocations_t,
                         {"pool_id": pool_id, "amount": amount}, ["pool_id"])

    def apply_reallocation(self, from_pool: str, to_pool: str, amount: float) -> None:
        with self._lock, self._engine.begin() as conn:
            conn.execute(update(allocations_t).where(allocations_t.c.pool_id == from_pool)
                         .values(amount=allocations_t.c.amount - amount))
            conn.execute(update(allocations_t).where(allocations_t.c.pool_id == to_pool)
                         .values(amount=allocations_t.c.amount + amount))

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

    # -- LLM usage budget (protect the reasoning API key) -----------------
    @staticmethod
    def _today() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    def llm_calls_today(self) -> int:
        raw = self._kv_get(f"llm_calls:{self._today()}")
        return int(raw) if raw else 0

    def incr_llm_call(self) -> int:
        key = f"llm_calls:{self._today()}"
        with self._lock, self._engine.begin() as conn:
            row = conn.execute(select(kv_t.c.value).where(kv_t.c.key == key)).first()
            n = (int(row[0]) if row else 0) + 1
            self._upsert(conn, kv_t, {"key": key, "value": str(n)}, ["key"])
        return n

    def _kv_get(self, key: str) -> Optional[str]:
        with self._engine.connect() as conn:
            row = conn.execute(select(kv_t.c.value).where(kv_t.c.key == key)).first()
        return row[0] if row else None

    def _kv_set(self, key: str, value: str) -> None:
        with self._lock, self._engine.begin() as conn:
            self._upsert(conn, kv_t, {"key": key, "value": value}, ["key"])


_default: Optional[Store] = None


def get_store() -> Store:
    global _default
    if _default is None:
        _default = Store()
    return _default
