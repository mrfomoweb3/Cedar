"""Real MCP clients for the OBSERVE node.

Two providers, per CEDAR_BACKEND_BUILD.md Segment 2:

  * ``CsprTradeClient`` -- CSPR.trade MCP (public, no key). Streamable-HTTP / SSE
    JSON-RPC. Exposes real DEX pools, reserves, and price/volume history, from
    which we derive per-pool yield (fee APR) and an independent cross-check
    signal (price-return APR).

  * ``CasperCloudClient`` -- the community Casper MCP server (POST /mcp) for
    chain-state reads (balances / contract reads) and as the intended second
    APY source. Requires an X-CSPR-Cloud-Api-Key header (from cspr.cloud) and
    X-Casper-Network: testnet. Fully wired; raises clearly if the key is absent.

Yield derivation (documented, from real data only):
  fee_apr   = (recent_volume_token0 * FEE_RATE) annualized / TVL_token0
  price_apr = annualized open->close return over the returned candles
The DEX has no native APY field, so these are computed from real reserves +
real swap volume; both are clamped/handled by the VALIDATE node's range check.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

FEE_RATE = 0.003  # CSPR.trade AMM swap fee (0.3%), standard constant-product


class MCPError(RuntimeError):
    pass


class _StreamableMCP:
    """Minimal MCP streamable-HTTP client: initialize -> session -> tools/call.
    Parses SSE ('data: {json}') framing and returns the parsed tool JSON."""

    def __init__(self, url: str, headers: Optional[dict[str, str]] = None, timeout: float = 45.0):
        self.url = url
        self.extra_headers = headers or {}
        self.timeout = timeout
        self._session_id: Optional[str] = None
        self._client = httpx.Client(timeout=timeout)

    def _base_headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        h.update(self.extra_headers)
        if self._session_id:
            h["mcp-session-id"] = self._session_id
        return h

    @staticmethod
    def _parse_sse(text: str) -> dict[str, Any]:
        lines = [ln[6:] for ln in text.splitlines() if ln.startswith("data: ")]
        if not lines:
            # plain JSON (non-SSE) fallback
            return json.loads(text) if text.strip() else {}
        return json.loads(lines[-1])

    def initialize(self) -> None:
        resp = self._client.post(self.url, headers=self._base_headers(), json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "cedar", "version": "1.0"}},
        })
        resp.raise_for_status()
        self._session_id = resp.headers.get("mcp-session-id")
        # notify initialized (best-effort)
        try:
            self._client.post(self.url, headers=self._base_headers(),
                              json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            pass

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._session_id is None:
            self.initialize()
        resp = self._client.post(self.url, headers=self._base_headers(), json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        resp.raise_for_status()
        data = self._parse_sse(resp.text)
        if "error" in data:
            raise MCPError(f"{name}: {data['error']}")
        result = data.get("result", {})
        content = result.get("content")
        if content and isinstance(content, list) and content[0].get("type") == "text":
            txt = content[0]["text"]
            try:
                return json.loads(txt)
            except json.JSONDecodeError:
                raise MCPError(f"{name} returned non-JSON text: {txt[:200]}")
        return result

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# CSPR.trade
# ---------------------------------------------------------------------------
class CsprTradeClient:
    def __init__(self, url: Optional[str] = None):
        self.url = url or os.getenv("CSPR_TRADE_MCP_URL", "https://mcp.cspr.trade/mcp")
        self._mcp = _StreamableMCP(self.url)

    def get_pairs(self) -> list[dict[str, Any]]:
        res = self._mcp.call("get_pairs", {})
        return res.get("data", res if isinstance(res, list) else [])

    def get_pair_price_history(self, pair: str) -> list[dict[str, Any]]:
        res = self._mcp.call("get_pair_price_history", {"pair": pair})
        return res if isinstance(res, list) else res.get("data", [])

    # -- yield derivation --------------------------------------------------
    @staticmethod
    def _tvl_token0(pair: dict[str, Any]) -> float:
        # reserves are integer base units at token decimals; token0 units suffice
        d0 = pair["token0"].get("decimals", 9)
        return int(pair.get("reserve0", 0)) / (10 ** d0)

    def fee_apr(self, pair: dict[str, Any], history: list[dict[str, Any]]) -> float:
        """Annualized LP fee yield from real swap volume and reserves."""
        tvl0 = self._tvl_token0(pair)
        if tvl0 <= 0 or not history:
            return 0.0
        # volume in token0 units across the returned window
        vol0 = sum(float(c.get("volumeToken0", 0) or 0) for c in history)
        span = self._history_span_days(history)
        if span <= 0:
            return 0.0
        daily_fees = (vol0 * FEE_RATE) / span
        return (daily_fees * 365.0) / tvl0 * 100.0

    @staticmethod
    def price_apr(history: list[dict[str, Any]]) -> float:
        """Independent cross-check: annualized open->close price return."""
        if len(history) < 2:
            return 0.0
        first_open = float(history[0].get("open") or 0)
        last_close = float(history[-1].get("close") or 0)
        if first_open <= 0:
            return 0.0
        span = CsprTradeClient._history_span_days(history)
        if span <= 0:
            return 0.0
        total_return = (last_close - first_open) / first_open
        return total_return / span * 365.0 * 100.0

    @staticmethod
    def _history_span_days(history: list[dict[str, Any]]) -> float:
        try:
            t0 = _parse_ts(history[0]["timestamp"])
            t1 = _parse_ts(history[-1]["timestamp"])
            days = (t1 - t0) / 86400.0
            return max(days, 1.0 / 24.0)  # floor at 1h to avoid div blow-ups
        except Exception:
            return 1.0

    def close(self) -> None:
        self._mcp.close()


# ---------------------------------------------------------------------------
# Casper MCP (cspr.cloud) — chain state + intended 2nd APY source
# ---------------------------------------------------------------------------
class CasperCloudClient:
    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None,
                 network: Optional[str] = None):
        self.url = url or os.getenv("CASPER_MCP_URL", "")
        self.api_key = api_key or os.getenv("CSPR_CLOUD_API_KEY", "")
        self.network = network or os.getenv("X_CASPER_NETWORK", "testnet")
        if not self.url or not self.api_key:
            raise MCPError(
                "CasperCloudClient needs CASPER_MCP_URL + CSPR_CLOUD_API_KEY "
                "(get a key at cspr.cloud). Header X-Casper-Network defaults to testnet.")
        self._mcp = _StreamableMCP(self.url, headers={
            "X-CSPR-Cloud-Api-Key": self.api_key,
            "X-Casper-Network": self.network,
        })

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        return self._mcp.call(name, arguments)

    def close(self) -> None:
        self._mcp.close()


def _parse_ts(s: str) -> float:
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() \
        if "+" not in s else datetime.fromisoformat(s).timestamp()


if __name__ == "__main__":
    # Calibration: print real derived yields for the live pools.
    c = CsprTradeClient()
    pairs = c.get_pairs()
    print(f"{len(pairs)} pairs live")
    rows = []
    for p in pairs:
        sym = f"{p['token0']['symbol']}/{p['token1']['symbol']}"
        try:
            hist = c.get_pair_price_history(p["contractPackageHash"])
        except Exception as e:
            print(f"  {sym}: history error {e}")
            continue
        fee = c.fee_apr(p, hist)
        price = c.price_apr(hist)
        tvl = c._tvl_token0(p)
        rows.append((sym, p["contractPackageHash"][:10], tvl, fee, price, len(hist)))
    rows.sort(key=lambda r: r[2], reverse=True)
    print(f"\n{'pair':<18}{'hash':<12}{'tvl_tok0':>16}{'fee_apr%':>12}{'price_apr%':>12}{'candles':>9}")
    for sym, h, tvl, fee, price, n in rows:
        print(f"{sym:<18}{h:<12}{tvl:>16.2f}{fee:>12.2f}{price:>12.2f}{n:>9}")
    c.close()
