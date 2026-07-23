"""Chain-write adapter.

Signs and submits the ``reallocate`` call to the deployed VaultRouter contract.
A ``Signer`` protocol with three implementations:

  * ``MockSigner``       -- deterministic synthetic tx hash; drives dev/tests/demo.
  * ``CasperKeySigner``  -- REAL server-side signing. Shells out to casper-client
    to submit a ``reallocate`` deploy against the live contract package and
    returns the real deploy hash. This is what makes the autonomous loop actuate
    on Casper Testnet without a human in the loop (CSPR.click is a browser wallet
    SDK and can't be driven server-side).
  * ``CsprClickSigner``  -- config-name alias of CasperKeySigner (so
    CEDAR_SIGNER=csprclick still resolves). Server-side signing is the sole,
    deliberate actuation path; there is no separate CSPR.click implementation
    because a browser wallet SDK can't be driven by a headless autonomous loop.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from typing import Optional, Protocol

from .types import POOL_IDS

# PoolId is a fieldless Odra enum -> encoded on-chain as u8.
POOL_INDEX = {pid: i for i, pid in enumerate(POOL_IDS)}  # PoolA=0, PoolB=1, PoolC=2


_PEM_RE = re.compile(r"-----BEGIN[\s\S]*?-----END[^\n]*-----")
# base64 runs of 100+ chars catch an encoded .pem (~296 chars) without touching
# 64-char tx hashes or ordinary text.
_B64_RE = re.compile(r"[A-Za-z0-9+/]{100,}={0,2}")


def redact_secrets(text: Optional[str]) -> Optional[str]:
    """Strip anything resembling key material (PEM blocks, long base64 runs) from
    a string before it is stored or served. Defense against a tool echoing the
    signing key into an error that would otherwise reach the public feed/audit."""
    if not text:
        return text
    text = _PEM_RE.sub("[redacted-key]", text)
    text = _B64_RE.sub("[redacted]", text)
    return text


def _materialize_pem(data: bytes) -> str:
    """Write PEM bytes to a private temp file and return its path.

    casper-client can only read the key from a file, so a file is unavoidable;
    it is created 0600 atomically (no open→chmod window) inside a fresh 0700
    directory, so no other user can ever observe the bytes.
    """
    import tempfile
    keydir = os.path.join(tempfile.gettempdir(), "cedar_keys")
    os.makedirs(keydir, mode=0o700, exist_ok=True)
    os.chmod(keydir, 0o700)
    path = os.path.join(keydir, "casper_secret_key.pem")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return path


def _resolve_secret_key(raw: str) -> str:
    """Resolve the signing key to a filesystem path, tolerant of how a host
    supplies it. ``casper-client`` needs a *file path*, but cloud dashboards
    can't mount a .pem, so a key may arrive as:

      * a file path (used as-is),
      * raw PEM text pasted into ``CASPER_SECRET_KEY``,
      * base64 of the .pem in ``CASPER_SECRET_KEY_B64`` **or** (a common mix-up)
        pasted straight into ``CASPER_SECRET_KEY``.

    Any non-path form is decoded and materialised to a private temp file, so a
    misplaced value still works instead of failing with 'file name too long'.
    """
    import base64

    raw = (raw or "").strip().strip('"').strip("'")
    # 1. an actual file path wins
    if raw and os.path.isfile(raw):
        return raw

    # 2. resolve PEM bytes from whatever we were handed, in priority order
    for candidate in (raw, (os.getenv("CASPER_SECRET_KEY_B64") or "").strip()):
        if not candidate:
            continue
        if candidate.startswith("-----BEGIN"):           # raw PEM text
            return _materialize_pem(candidate.encode())
        try:                                             # base64-encoded PEM
            data = base64.b64decode(candidate, validate=True)
        except Exception:  # noqa: BLE001
            continue
        if data.startswith(b"-----BEGIN") or b"PRIVATE KEY" in data[:80]:
            return _materialize_pem(data)

    return raw


def _resolve_client_bin() -> str:
    """Resolve the casper-client path, tolerant of a misconfigured env var
    (e.g. an inline comment leaking through .env parsing). Falls back to the
    cargo install path, then bare 'casper-client' on PATH."""
    raw = (os.getenv("CASPER_CLIENT_BIN") or "").split("#", 1)[0].strip()
    default = os.path.expanduser("~/.cargo/bin/casper-client")
    for cand in (raw, default):
        if cand and os.path.isfile(cand):
            return cand
    return "casper-client"


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


class CasperKeySigner:
    """Real server-side signer. Submits ``reallocate`` to the live VaultRouter via
    casper-client and returns the deploy hash.

    Config (env, overridable):
      CASPER_NODE_URL      RPC endpoint            (default: testnet public node)
      CASPER_CHAIN         chain name              (default: casper-test)
      CASPER_SECRET_KEY    path to secret_key.pem
      VAULT_ROUTER_HASH    contract package hash   (hash-… from deploy)
      CASPER_CLIENT_BIN    casper-client path      (default: casper-client on PATH)
      CASPER_CALL_PAYMENT  motes for the call      (default: 5 CSPR)
      CEDAR_CONFIRM_TX     "1" to block until the deploy executes (default: off)
    """

    def __init__(self, *, node_url: Optional[str] = None, chain: Optional[str] = None,
                 secret_key: Optional[str] = None, contract_hash: Optional[str] = None,
                 client_bin: Optional[str] = None):
        self.node_url = node_url or os.getenv("CASPER_NODE_URL",
                                              "https://node.testnet.casper.network/rpc")
        self.chain = chain or os.getenv("CASPER_CHAIN", "casper-test")
        self.secret_key = _resolve_secret_key(secret_key or os.getenv("CASPER_SECRET_KEY", ""))
        self.contract_hash = contract_hash or os.getenv("VAULT_ROUTER_HASH", "")
        self.client_bin = client_bin or _resolve_client_bin()
        self.payment = os.getenv("CASPER_CALL_PAYMENT", "5000000000")
        self.confirm = os.getenv("CEDAR_CONFIRM_TX", "0") == "1"
        if not self.secret_key or not self.contract_hash:
            raise ValueError("CasperKeySigner requires CASPER_SECRET_KEY and VAULT_ROUTER_HASH")

    def _run(self, args: list[str]) -> dict:
        proc = subprocess.run([self.client_bin, *args], capture_output=True, text=True, timeout=90)
        if proc.returncode != 0:
            detail = redact_secrets(proc.stderr.strip() or proc.stdout.strip())
            raise RuntimeError(f"casper-client failed: {detail}")
        # casper-client prepends a deprecation banner for put-deploy; extract JSON.
        out = proc.stdout
        start = out.find("{")
        return json.loads(out[start:]) if start >= 0 else {}

    def reallocate(self, from_pool: str, to_pool: str, amount: float) -> str:
        if from_pool not in POOL_INDEX or to_pool not in POOL_INDEX:
            raise ValueError(f"unknown pool: {from_pool} / {to_pool}")
        # CEDAR_MOTES_SCALE maps the agent's CSPR-denominated amount to the
        # contract's stored units: 1 for v2 (whole units), 1e9 for v3 (motes).
        scale = float(os.getenv("CEDAR_MOTES_SCALE", "1") or "1")
        amt = int(round(amount * scale))
        result = self._run([
            "put-deploy",
            "--node-address", self.node_url,
            "--chain-name", self.chain,
            "--secret-key", self.secret_key,
            "--payment-amount", self.payment,
            "--session-package-hash", self.contract_hash,
            "--session-entry-point", "reallocate",
            "--session-arg", f"from_pool:u8='{POOL_INDEX[from_pool]}'",
            "--session-arg", f"to_pool:u8='{POOL_INDEX[to_pool]}'",
            "--session-arg", f"amount:u512='{amt}'",
        ])
        deploy_hash = result.get("result", {}).get("deploy_hash")
        if not deploy_hash:
            raise RuntimeError(f"no deploy_hash in response: {result}")
        if self.confirm:
            self._await_execution(deploy_hash)
        return deploy_hash

    def _await_execution(self, deploy_hash: str, tries: int = 20, delay: float = 6.0) -> None:
        for _ in range(tries):
            time.sleep(delay)
            try:
                res = self._run(["get-deploy", "--node-address", self.node_url, deploy_hash])
            except Exception:
                continue
            info = (res.get("result", {}).get("execution_info") or {})
            er = info.get("execution_result")
            if not er:
                continue
            v2 = er.get("Version2") or {}
            msg = v2.get("error_message")
            if msg:
                raise RuntimeError(f"reallocate reverted on-chain: {msg}")
            return
        raise RuntimeError(f"reallocate {deploy_hash} not executed within timeout")


# Backwards-compatible alias for the documented CSPR.click seam.
CsprClickSigner = CasperKeySigner


def explorer_url(tx_hash: str) -> str:
    base = os.getenv("CASPER_EXPLORER_TX", "https://testnet.cspr.live/deploy/")
    return f"{base}{tx_hash}"


def get_default_signer() -> Signer:
    choice = os.getenv("CEDAR_SIGNER", "mock").lower()
    if choice in ("casper", "key", "csprclick"):
        return CasperKeySigner()
    return MockSigner()
