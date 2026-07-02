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

## Frontend (dashboard)

Dark-mode fintech-terminal UI (Vite + React + TS + recharts) built to make the
agent's autonomy *visible* — the live reasoning feed is the hero, and refusals
are rendered as prominently as executions. Six screens: Live Dashboard,
Portfolio, Guardrails & Safety, Audit Log, Policy Settings, Onboarding.

```bash
# with the API running on :8000
cd frontend
npm install
npm run dev            # http://localhost:5173  (VITE_API_BASE defaults to :8000)
```

The Dashboard's **Spike APY** / **Bad Data** / **Run Cycle** buttons drive the two
demo scenarios live on camera. Executed cycles show a copyable tx hash linking to
the Casper testnet explorer; blocked cycles show the named guardrail that fired.

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

**Testnet contract address (LIVE):**
[`hash-27131991…e850e493`](https://testnet.cspr.live/contract-package/27131991299036f9116c2754a042d682e50dfd4fe66e84c64111b3dae850e493)
— deployed to `casper-test`, with verifiable `deposit` + `reallocate` transactions.
See [DEPLOYMENT.md](DEPLOYMENT.md) for all hashes and explorer links.

## Real chain integration (verified live)

A full cycle has run end-to-end against real infrastructure — real reads, real
reasoning, real on-chain actuation:

- **Reads — CSPR.trade MCP** (`https://mcp.cspr.trade/mcp`, public, testnet):
  OBSERVE maps the 3 highest-TVL, actively-traded DEX pools → PoolA/B/C and
  derives each pool's **fee APR** from real reserves + real swap volume (the DEX
  exposes no native APY field). Verified live: WCSPR/sCSPR 0.44%, CD_LONG/WCSPR
  1.07%, WCSPR/CD_SHORT 9.18%.
- **Writes — server-side Casper signer**: ACTUATE signs + submits the real
  `reallocate` deploy to the live VaultRouter and captures the tx hash. Example
  autonomous cycle: reallocated 250 PoolA→PoolC (Δ 8.74pp), tx
  [`f79ba36f…`](https://testnet.cspr.live/deploy/f79ba36fc0a4541be4995cff59ce4146657d82b7973fa96fb1ae485b8864f99c).

Enable with `CEDAR_DATA_SOURCE=casper CEDAR_SIGNER=casper` (see `.env.example`).

**Actuation is server-side signing only, by design.** A browser wallet SDK
(CSPR.click) can't be driven by a headless autonomous loop, so ACTUATE signs with
the agent's own key via casper-client. This is the deliberate, sole write path —
there is no human-in-the-loop signing step.

**Two honest caveats.** (1) The community **Casper MCP** server (chain reads +
the intended *second* APY source for the cross-provider divergence check) needs a
cspr.cloud API key — the client is fully wired (`agent/mcp_real.py`,
`CasperCloudClient`) and gated on `CSPR_CLOUD_API_KEY`; until it's set the
cross-source check mirrors the primary reading. (2) CSPR.trade has no native APY,
so yield is a derived fee APR — documented, computed from real data.

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
