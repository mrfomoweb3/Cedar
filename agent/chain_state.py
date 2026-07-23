"""On-chain allocation read-back for the OBSERVE node.

Reads the VaultRouter's ``allocations`` Mapping directly from Casper global
state via JSON-RPC, so each cycle observes chain truth instead of trusting the
local SQLite cache. (The cache remains as write-through state for the UI and as
a fallback if the RPC is unreachable — the fallback is logged, never silent.)

Odra 2.x storage layout (verified empirically against the deployed contract):
  - contract named key "state" holds the storage dictionary
  - item key = hex( blake2b256( field_index_be_u32 ++ to_bytes(mapping_key) ) )
  - module fields are indexed from 1 in declaration order:
      VaultRouter { owner: Var<Address> (idx 1), allocations: Mapping (idx 2) }
  - stored value is CLValue List<U8> wrapping ToBytes(U512):
      [num_bytes, little-endian bytes...]
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Callable, Optional

import httpx

from .types import POOL_IDS

log = logging.getLogger("cedar.chain_state")

ALLOCATIONS_FIELD_INDEX = int(os.getenv("CEDAR_ALLOC_FIELD_INDEX", "2"))


def _motes_scale() -> float:
    """Divisor mapping the contract's stored units to the agent's CSPR units.
    1 = the contract stores whole units (v2, records-only). 1e9 = the contract
    stores motes (v3, real CSPR custody), so read-back is scaled to whole CSPR."""
    return float(os.getenv("CEDAR_MOTES_SCALE", "1") or "1")


class ChainAllocationReader:
    def __init__(self, node_url: Optional[str] = None,
                 package_hash: Optional[str] = None):
        self.node_url = node_url or os.getenv(
            "CASPER_NODE_URL", "https://node.testnet.casper.network/rpc")
        self.package_hash = (package_hash or os.getenv("VAULT_ROUTER_HASH", "")).strip()
        if not self.package_hash:
            raise ValueError("ChainAllocationReader requires VAULT_ROUTER_HASH")
        self._contract_hash: Optional[str] = None
        self._client = httpx.Client(timeout=30.0)

    def _rpc(self, method: str, params: dict) -> dict:
        resp = self._client.post(self.node_url, json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"{method}: {data['error']}")
        return data["result"]

    def _state_root(self) -> str:
        return self._rpc("chain_get_state_root_hash", {})["state_root_hash"]

    def _resolve_contract_hash(self, state_root: str) -> str:
        """Package hash -> newest enabled contract version's contract hash."""
        if self._contract_hash:
            return self._contract_hash
        res = self._rpc("query_global_state", {
            "state_identifier": {"StateRootHash": state_root},
            "key": self.package_hash, "path": [],
        })
        pkg = res["stored_value"].get("ContractPackage") or {}
        versions = pkg.get("versions") or []
        if not versions:
            raise RuntimeError(f"no contract versions in package {self.package_hash}")
        self._contract_hash = versions[-1]["contract_hash"].replace("contract-", "hash-")
        return self._contract_hash

    @staticmethod
    def _item_key(pool_index: int) -> str:
        data = ALLOCATIONS_FIELD_INDEX.to_bytes(4, "big") + bytes([pool_index])
        return hashlib.blake2b(data, digest_size=32).hexdigest()

    @staticmethod
    def _decode_u512(cl_value: dict) -> float:
        raw = bytes.fromhex(cl_value["bytes"])
        # List<U8> layout: u32 LE length prefix, then ToBytes(U512) = [n, le...]
        body = raw[4:]
        if not body:
            return 0.0
        n = body[0]
        return float(int.from_bytes(body[1:1 + n], "little"))

    def get_allocations(self) -> dict[str, float]:
        """Read every pool's on-chain allocation. Raises on RPC failure."""
        srh = self._state_root()
        contract = self._resolve_contract_hash(srh)
        out: dict[str, float] = {}
        for i, pid in enumerate(POOL_IDS):
            try:
                res = self._rpc("state_get_dictionary_item", {
                    "state_root_hash": srh,
                    "dictionary_identifier": {"ContractNamedKey": {
                        "key": contract, "dictionary_name": "state",
                        "dictionary_item_key": self._item_key(i)}},
                })
                out[pid] = self._decode_u512(res["stored_value"]["CLValue"]) / _motes_scale()
            except RuntimeError as exc:
                # "value not found" == never written == 0 (get_or_default)
                if "not found" in str(exc).lower():
                    out[pid] = 0.0
                else:
                    raise
        return out


def make_allocations_provider(store) -> Callable[[], dict[str, float]]:
    """Chain-truth allocations provider with a LOGGED fallback to the local
    cache. Also reconciles the cache to chain on every successful read so the
    portfolio endpoint reflects on-chain state."""
    if not os.getenv("VAULT_ROUTER_HASH", "").strip() or \
            os.getenv("CEDAR_CHAIN_READ", "1") == "0":
        return store.get_allocations

    reader = ChainAllocationReader()

    def provider() -> dict[str, float]:
        try:
            chain = reader.get_allocations()
        except Exception as exc:  # noqa: BLE001
            log.warning("chain allocation read FAILED (%s); falling back to "
                        "local cache — values may be stale", exc)
            return store.get_allocations()
        # reconcile local cache to chain truth
        cached = store.get_allocations()
        for pid, amt in chain.items():
            if abs(cached.get(pid, 0.0) - amt) > 1e-9:
                store.set_allocation(pid, amt)
        return chain

    return provider
