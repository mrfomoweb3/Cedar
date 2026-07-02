"""Segment 6 test gate: endpoints return real store data; pause halts the loop."""
import os

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the app at an isolated DB and disable autostart before import.
    monkeypatch.setenv("CEDAR_DB", str(tmp_path / "api.db"))
    monkeypatch.setenv("CEDAR_AUTOSTART", "0")
    monkeypatch.setenv("CEDAR_DATA_SOURCE", "mock")
    monkeypatch.setenv("CEDAR_SIGNER", "mock")
    # Fresh import so module-level store/agent bind to the temp DB.
    import importlib
    import api.store as store_mod
    store_mod._default = None
    import api.main as main_mod
    importlib.reload(main_mod)
    from fastapi.testclient import TestClient
    return TestClient(main_mod.app)


def test_status_endpoint(client):
    r = client.get("/agent/status")
    assert r.status_code == 200
    assert "status" in r.json()


def test_portfolio_endpoint(client):
    r = client.get("/agent/portfolio")
    body = r.json()
    assert body["total_value"] == sum(body["allocations"].values())


def test_run_once_then_feed(client):
    client.post("/agent/demo/spike")
    r = client.post("/agent/run-once")
    assert r.status_code == 200
    feed = client.get("/agent/feed").json()["cycles"]
    assert len(feed) >= 1
    assert feed[0]["outcome"] in {"EXECUTED", "HOLD", "BLOCKED", "VALIDATION_FAILED"}


def test_policy_roundtrip(client):
    p = client.get("/agent/policy").json()
    p["min_apy_delta"] = 3.5
    assert client.post("/agent/policy", json=p).status_code == 200
    assert client.get("/agent/policy").json()["min_apy_delta"] == 3.5


def test_pause_resume(client):
    assert client.post("/agent/pause").json()["paused"] is True
    assert client.get("/agent/status").json()["paused"] is True
    assert client.post("/agent/resume").json()["paused"] is False


def test_bad_data_demo_validation_failed(client):
    client.post("/agent/demo/bad-data")
    r = client.post("/agent/run-once").json()
    assert r["outcome"] == "VALIDATION_FAILED"
    assert r["tx_hash"] is None
