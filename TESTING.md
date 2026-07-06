# Testing Cedar — step-by-step (5 minutes)

Concise instructions to verify every claim. No setup needed for steps 1–4.

## 1. Verify the live autonomous agent (30s)

1. Open **https://trycedar.xyz/app**
2. The **Live Reasoning Feed** shows the agent's cycles: HOLD / BLOCKED / EXECUTED, each with plain-English reasoning.
3. `https://trycedar.xyz/healthz` should show `"signer":"casper"` — real on-chain signing.

## 2. Trigger a real on-chain transaction (60s)

1. On the dashboard, click **▲ Spike** (seeds a yield spike), then **▶ Run cycle**.
2. A new **EXECUTED** card appears with a tx hash.
3. Click the hash → it resolves on **testnet.cspr.live** (real deploy, not a mock).

## 3. Watch it refuse (60s)

1. Click **⚠ Bad data**, then **▶ Run cycle** → outcome **VALIDATION_FAILED** (a 9000% APY is rejected before the model sees it).
2. Run more cycles: small-delta moves are **BLOCKED** by `cost_check` with the exact numbers logged.

## 4. Verify the contract on-chain (60s)

- Contract package: [`2e027302…ae7b298d`](https://testnet.cspr.live/contract-package/2e02730283fb38e9ef03699ac81cb93e7c1194237d06b1cde95b4c12ae7b298d)
- Sample autonomous reallocation: [`d8d6c9fd…e6d33172`](https://testnet.cspr.live/deploy/d8d6c9fdb51b48a0a6d5fffb0b39309b30ddbc058a95ed1fda247c18e6d33172) — `reallocate`, executed without error, signed by the agent's owner key.
- All state-changing entrypoints are owner-gated ([contracts/vault_router/src/lib.rs](contracts/vault_router/src/lib.rs), `assert_owner`).

## 5. Run it locally (2 min, fully offline, no keys)

```bash
git clone https://github.com/mrfomoweb3/Cedar.git && cd Cedar
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                                      # 50 tests pass
cp .env.example .env
uvicorn api.main:app                            # http://localhost:8000
curl -X POST localhost:8000/agent/demo/spike
curl -X POST localhost:8000/agent/run-once      # → EXECUTED (mock signer)
curl -X POST localhost:8000/agent/demo/bad-data
curl -X POST localhost:8000/agent/run-once      # → VALIDATION_FAILED
curl      localhost:8000/agent/feed             # full decision log
```

No API keys required — without `GROQ_API_KEY` the reason node falls back to the deterministic engine (flagged in the trace), so the entire pipeline is testable offline.
