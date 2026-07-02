import os
import tempfile

import pytest

from agent.cspr_click import MockSigner
from agent.graph import build_default_agent
from agent.mcp_clients import MockMarketDataSource
from api.store import Store


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))


@pytest.fixture()
def source():
    return MockMarketDataSource(seed=7)


@pytest.fixture()
def signer():
    return MockSigner()


@pytest.fixture()
def agent(store, source, signer):
    # force_deterministic keeps tests offline & reproducible (no LLM calls).
    return build_default_agent(store, force_deterministic=True,
                               source=source, signer=signer)
