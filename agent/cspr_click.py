"""Chain-write adapter: CSPR.click AI Agent Skill.

Signs and submits the ``reallocate`` call to the deployed VaultRouter contract.
As with the read side, a ``Signer`` protocol with a mock (returns a synthetic
but explorer-shaped tx hash) and a real seam for CSPR.click.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Optional, Protocol

from .types import Policy  # noqa: F401  (kept for future signature typing)


class Signer(Protocol):
    def reallocate(self, from_pool: str, to_pool: str, amount: float) -> str:
        """Submit a reallocate tx; return the tx hash. Raise on failure."""
        ...


class MockSigner:
    """Deterministic mock. Produces a realistic 64-hex tx hash and can be told
    to fail once (to exercise the EXECUTION_FAILED path)."""

    def __init__(self):
        self._fail_next = False

    def fail_next(self) -> None:
        self._fail_next = True

    def reallocate(self, from_pool: str, to_pool: str, amount: float) -> str:
        if self._fail_next:
            self._fail_next = False
            raise RuntimeError("simulated network error submitting reallocate tx")
        payload = f"{from_pool}->{to_pool}:{amount}:{time.time()}".encode()
        return hashlib.sha256(payload).hexdigest()


class CsprClickSigner:
    """Real adapter over the CSPR.click AI Agent Skill. Wire signing + submit
    to the deployed VaultRouter here once wallet creds are configured."""

    def __init__(self, contract_hash: Optional[str] = None,
                 node_url: Optional[str] = None):
        self.contract_hash = contract_hash or os.getenv("VAULT_ROUTER_HASH", "")
        self.node_url = node_url or os.getenv("CASPER_NODE_URL", "")

    def reallocate(self, from_pool: str, to_pool: str, amount: float) -> str:  # pragma: no cover
        raise NotImplementedError(
            "Wire CSPR.click AI Agent Skill: build the reallocate deploy against "
            "VAULT_ROUTER_HASH, sign, submit, return the deploy/tx hash."
        )


def explorer_url(tx_hash: str) -> str:
    base = os.getenv("CASPER_EXPLORER_TX", "https://testnet.cspr.live/deploy/")
    return f"{base}{tx_hash}"


def get_default_signer() -> Signer:
    if os.getenv("CEDAR_SIGNER", "mock").lower() == "csprclick":
        return CsprClickSigner()
    return MockSigner()
