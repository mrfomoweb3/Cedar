# Cedar — Autonomous Yield-Routing Agent

Cedar is an autonomous agent for the **Casper Agentic Buildathon 2026**. It watches
pool yields on Casper, decides whether to move capital, and — with no human in the
loop — signs and submits a real on-chain reallocation. Every action is gated by a
defense-in-depth safety pipeline, and every decision (including refusals) is logged.

The core thesis: **an autonomous agent that touches money is only as good as the
things it refuses to do.** Cedar's architecture is built around that.

## The autonomous loop

```
[OBSERVE] → [VALIDATE] → [REASON] → [RECHECK] → [GUARDRAILS] → [ACTUATE]
                 │            │           │            │             │
              (fail)      force-HOLD   disagree     any fail     tx hash
                 └────────────┴───────────┴────────────┴─────────────┘
                                        ▼
                                   [LOG]  (runs on every path)
```

No confirm button sits between REASON and ACTUATE. Safety comes from the pipeline,
not from a human clicking "yes":

1. **OBSERVE** — pull per-pool APY, on-chain allocation, and a gas estimate from the
   Casper MCP Server + CSPR.trade MCP into a typed `MarketSnapshot`.
2. **VALIDATE** — the bad-data guardrail. Range-checks APYs (a 9000% reading is bad
   data, not a jackpot), rejects stale snapshots, and **halts on cross-source
   divergence rather than averaging**.
3. **REASON** — a schema-constrained Claude call that sees *only* the validated
   snapshot + policy. Its JSON output is then hard-checked in code: unknown pools,
   over-cap amounts, and fabricated figures all force a HOLD. No second LLM call.
4. **RECHECK** — a deterministic, non-LLM re-derivation of the same decision. If the
   dumb rule and the model disagree, Cedar force-HOLDs. They should always agree;
   the disagreement path is the last line of defense.
5. **GUARDRAILS** — cooldown, position cap, cost-vs-gain, and a final anomaly pass.
   First failure short-circuits to a logged, named refusal.
6. **ACTUATE** — only if everything passes. Signs + submits `reallocate` via the
   CSPR.click AI Agent Skill and captures the tx hash. Failures are surfaced, never
   silently retried (no double-spend).
7. **LOG** — one record per cycle powers both the live dashboard feed and the audit
   log.

## Repo layout

```
contracts/vault_router/   Odra smart contract (deposit / reallocate / views) + tests
agent/
  graph.py                LangGraph StateGraph wiring the pipeline above
  types.py                typed state, policy, snapshot, decision models
  decision.py             deterministic decision engine (recheck + fallback)
  mcp_clients.py          Casper/CSPR.trade read adapters (mock + real seam)
  cspr_click.py           CSPR.click write adapter (mock + real seam)
  scheduler.py            fixed-interval loop runner with pause/resume
  nodes/                  observe · validate · reason · recheck · guardrails · actuate · log
api/
  main.py                 FastAPI control plane + dashboard endpoints
  store.py                SQLite store (cycle log, policy, allocations, run-state)
tests/                    per-segment test gates (28 tests)
scripts/                  deploy_contract.sh · seed_demo.py
```

## Quickstart (backend, fully offline)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# run the test suite (all segment gates)
pytest -q

# seed and run the demo scenarios in-process (no server, no chain)
python scripts/seed_demo.py --local

# or run the live API + autonomous loop
cp .env.example .env
uvicorn api.main:app --reload
```

With no `ANTHROPIC_API_KEY` set, the REASON node transparently falls back to the
deterministic engine so the whole loop runs offline. Set the key (and
`CEDAR_MODEL`) to put Claude in the loop; the code-side output guards apply either
way.

### Demo controls

```bash
curl -X POST localhost:8000/agent/demo/spike     # APY spike  → expect EXECUTED
curl -X POST localhost:8000/agent/demo/bad-data  # 9000% APY  → expect VALIDATION_FAILED
curl -X POST localhost:8000/agent/run-once       # run one cycle now
curl      localhost:8000/agent/feed              # live reasoning feed
curl -X POST localhost:8000/agent/pause          # kill switch
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET  | `/agent/status`    | current state + next-cycle countdown |
| GET  | `/agent/feed`      | recent cycle log (dashboard feed) |
| GET  | `/agent/portfolio` | allocation across pools + total value |
| GET  | `/agent/guardrails`| guardrail config + trigger counts + history |
| GET  | `/agent/audit`     | full paginated audit log |
| GET/POST | `/agent/policy`| read / update the active policy |
| POST | `/agent/pause` · `/agent/resume` | kill switch |
| POST | `/agent/onboard`   | initial policy + wallet connect |
| POST | `/agent/run-once`  | run a single cycle now |
| POST | `/agent/demo/{name}` | seed a demo scenario (`spike` · `bad-data` · `divergence`) |

## Smart contract — `VaultRouter` (Odra, Casper Testnet)

Minimal by design (`contracts/vault_router/src/lib.rs`):

- `deposit(pool_id, amount)` → records allocation, emits `Deposited`
- `reallocate(from_pool, to_pool, amount)` → moves allocation, emits `Reallocated`
  — **the transaction-producing on-chain action**
- `get_allocation(pool_id) -> U512` · `get_total_value() -> U512` — views

Pools are a fixed three-member enum (`PoolA/B/C`), matching the pre-vetted pool list.

```bash
# native unit tests (Odra MockVM)
cd contracts/vault_router && cargo test

# build wasm + deploy to testnet (needs cargo-odra, casper-client, a funded key)
cargo install cargo-odra
scripts/deploy_contract.sh
```

Record the deployed contract hash into `VAULT_ROUTER_HASH` (see `.env.example`);
the CSPR.click signer targets it for the real `reallocate` submission.

**Testnet contract address:** _TODO — paste hash after `scripts/deploy_contract.sh`_

## Mock ↔ real seams

The graph depends only on a `MarketDataSource` (read) and a `Signer` (write)
protocol. `MockMarketDataSource` / `MockSigner` drive dev, tests, and the offline
demo; `CasperMCPDataSource` / `CsprClickSigner` are API-compatible stubs to wire the
real Casper MCP + CSPR.click endpoints. Switch via `CEDAR_DATA_SOURCE` /
`CEDAR_SIGNER` — nothing else changes.

## Where the safety design lives (for reviewers)

- Bad-data guardrail → [`agent/nodes/validate.py`](agent/nodes/validate.py)
- Grounded reasoning + code-side output guards → [`agent/nodes/reason.py`](agent/nodes/reason.py)
- Deterministic recheck → [`agent/nodes/recheck.py`](agent/nodes/recheck.py) + [`agent/decision.py`](agent/decision.py)
- Cooldown / position-cap / cost / anomaly guardrails → [`agent/nodes/guardrails.py`](agent/nodes/guardrails.py)
- Every-path logging → [`agent/nodes/log.py`](agent/nodes/log.py)
