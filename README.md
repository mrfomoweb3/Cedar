<div align="center">

# 🌲 Cedar — Autonomous Yield-Routing Agent

**An autonomous agent that moves capital on Casper — and knows when to refuse.**

Cedar observes DeFi pool yields on Casper, reasons over them with an LLM, and — with **no human in the loop** — signs and submits real on-chain reallocations to an owner-gated smart contract. Every action clears a defense-in-depth safety pipeline; every decision, including every refusal, is logged and auditable.

[![Live](https://img.shields.io/badge/live-trycedar.xyz-1A5C2E)](https://trycedar.xyz)
[![Network](https://img.shields.io/badge/network-Casper%20Testnet-blue)](https://testnet.cspr.live/contract-package/dc10056192be60ae8db84e0b24e27629aec44381ba41b3bebfc89501b1828135)
[![Reasoning](https://img.shields.io/badge/reasoning-Groq%20·%20Llama%203.3-orange)](https://groq.com)
[![Contract](https://img.shields.io/badge/contract-Odra%20·%20Rust-red)](contracts/vault_router/src/lib.rs)
[![Tests](https://img.shields.io/badge/tests-43%20passing-brightgreen)](tests/)

[**Live app**](https://trycedar.xyz) · [**Docs**](https://trycedar.xyz/docs) · [**Contract on explorer**](https://testnet.cspr.live/contract-package/dc10056192be60ae8db84e0b24e27629aec44381ba41b3bebfc89501b1828135) · [**On-chain record**](DEPLOYMENT.md)

</div>

---

## Table of contents

- [Why Cedar](#why-cedar)
- [The autonomous loop](#the-autonomous-loop)
- [Architecture](#architecture)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Smart contract](#smart-contract--vaultrouter)
- [Safety design (for reviewers)](#safety-design-for-reviewers)
- [Cost controls](#cost-controls)
- [Deployment](#deployment)
- [Tech stack](#tech-stack)
- [Project layout](#project-layout)
- [Roadmap](#roadmap)

---

## Why Cedar

The core thesis: **an autonomous agent that touches money is only as good as the things it refuses to do.**

Most "AI agent" demos are a single LLM call wired straight to an action. Cedar is the opposite — the LLM is one link in a chain where **every other link can veto it**:

- Bad market data is rejected *before* the model ever sees it.
- The model sees **only** a validated snapshot — it cannot browse, recall, or invent.
- Its output is **hard-checked in code** — fabricated numbers, unknown pools, and over-cap amounts force a HOLD.
- A **deterministic, non-LLM engine independently re-derives** the decision; disagreement forces a HOLD.
- **Named guardrails** (cooldown, position cap, cost-vs-gain, anomaly) each get a final veto.
- **Every path** — action or refusal — is logged with full data provenance.

The durable asset isn't the yield router; it's the **safety pipeline**. Cedar is its reference implementation on Casper.

Built for the **Casper Agentic Buildathon 2026**.

---

## The autonomous loop

```
  ┌───────────┐   ┌────────────┐   ┌──────────┐   ┌───────────┐   ┌─────────────┐   ┌───────────┐
  │  OBSERVE  │──▶│  VALIDATE  │──▶│  REASON  │──▶│  RECHECK  │──▶│  GUARDRAILS │──▶│  ACTUATE  │
  └───────────┘   └────────────┘   └──────────┘   └───────────┘   └─────────────┘   └───────────┘
        │               │                │              │                │                 │
     read APY +      range /          LLM over      deterministic     cooldown ·       sign + submit
     on-chain        staleness /      validated     re-derivation ·   position cap ·   reallocate deploy,
     allocation      divergence       data only ·   disagree →        cost · anomaly · capture tx hash
                     → force-HOLD     code guards    force-HOLD        first fail → BLOCK
        │               │                │              │                │                 │
        └───────────────┴────────────────┴──────────────┴────────────────┴─────────────────┘
                                                  ▼
                                            ┌───────────┐
                                            │    LOG    │  one record per cycle → dashboard feed + audit log
                                            └───────────┘
```

**There is no confirm button between REASON and ACTUATE.** Safety comes from the pipeline, not from a human clicking "yes."

| # | Stage | What it does | Failure mode |
|---|-------|--------------|--------------|
| 1 | **OBSERVE** | Pull per-pool APY, on-chain allocation, and a gas estimate into a typed `MarketSnapshot`. Allocations are read **directly from contract storage**. | — |
| 2 | **VALIDATE** | Range-check APYs (a 9000% reading is bad data, not a jackpot), reject stale snapshots, **halt on cross-source divergence rather than averaging.** | `VALIDATION_FAILED` |
| 3 | **REASON** | Schema-constrained LLM call (Llama 3.3 on Groq) over *only* the validated snapshot + policy. Output is hard-checked in code. | force-`HOLD` |
| 4 | **RECHECK** | A deterministic, non-LLM engine re-derives the same decision. Disagreement is the last line of defense. | force-`HOLD` |
| 5 | **GUARDRAILS** | `cooldown` → `position_cap` → `cost_check` → `anomaly_recheck`. First failure short-circuits to a named, logged refusal. | `BLOCKED` |
| 6 | **ACTUATE** | Only if everything passes: sign + submit the `reallocate` deploy with the agent's key; capture the tx hash. Failures surfaced, never silently retried. | `EXECUTION_FAILED` |
| 7 | **LOG** | One record per cycle powers the live dashboard feed **and** the audit log. Runs on every path. | — |

---

## Architecture

```
                        ┌──────────────────────── Browser (trycedar.xyz) ────────────────────────┐
                        │  React 19 + Vite SPA   ·   / landing   ·   /app dashboard   ·   /docs   │
                        └───────────────────────────────────┬───────────────────────────────────┘
                                                             │  same-origin HTTPS (JSON)
                        ┌────────────────────────────────────▼──────────────────────────────────┐
                        │                    FastAPI control plane  (api/main.py)                 │
                        │   /agent/status · feed · portfolio · guardrails · audit · policy · …    │
                        │                     serves the built dashboard too                      │
                        └───────┬───────────────────────────────┬──────────────────────┬─────────┘
                                │                               │                      │
                 in-process     │                               │ SQLAlchemy           │ LangGraph
                 scheduler ─────┘                               ▼                      ▼
                 (fixed interval,                     ┌──────────────────┐   ┌────────────────────────┐
                  pause/resume)                       │  Store           │   │  Agent (StateGraph)    │
                                                      │  Postgres/SQLite │   │  observe→validate→…→log │
                                                      │  cycles·policy·  │   └───────┬────────┬───────┘
                                                      │  allocations     │           │        │
                                                      └──────────────────┘   reads   │        │ writes
                                                                                     ▼        ▼
                                              ┌────────────────────────────┐  ┌──────────────────────────┐
                                              │  MarketDataSource (read)   │  │   Signer (write)          │
                                              │  CSPR.trade MCP + Casper   │  │   casper-client →         │
                                              │  MCP · cross-source check  │  │   VaultRouter.reallocate  │
                                              └────────────────────────────┘  └──────────────────────────┘
                                                                                     │
                                                                          ┌──────────▼──────────┐
                                                                          │  Casper Testnet      │
                                                                          │  Odra VaultRouter    │
                                                                          └─────────────────────┘
```

The agent graph depends only on two protocols — `MarketDataSource` (read) and `Signer` (write). Mock implementations drive dev/tests/offline demos; the Casper implementations wire the real chain. **Switch with two env vars; nothing else changes.**

---

## Quickstart

### Prerequisites
- Python 3.12+
- Node 20+ (for the dashboard)
- *(optional, for real chain writes)* [`casper-client`](https://docs.casper.network/) 5.0.1 and a funded testnet key

### Backend (fully offline, no keys required)

```bash
git clone https://github.com/mrfomoweb3/Cedar.git && cd Cedar
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -q                         # run the full test suite (43 passing)
cp .env.example .env              # defaults run offline in mock mode
uvicorn api.main:app --reload     # http://localhost:8000
```

With no `GROQ_API_KEY` set, REASON transparently falls back to the deterministic engine, so the entire loop runs offline. Set the key to put a real model in the loop — the code-side output guards apply either way.

### Frontend (dashboard)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (VITE_API_BASE defaults to :8000)
```

### Try it in 30 seconds

```bash
curl -X POST localhost:8000/agent/demo/spike     # APY spike  → expect EXECUTED
curl -X POST localhost:8000/agent/demo/bad-data  # 9000% APY  → expect VALIDATION_FAILED
curl -X POST localhost:8000/agent/run-once       # run one cycle now
curl      localhost:8000/agent/feed              # live reasoning feed
curl -X POST localhost:8000/agent/pause          # kill switch
```

---

## Configuration

All configuration is via environment variables (see [`.env.example`](.env.example)).

### Reasoning (LLM)
| Variable | Default | Purpose |
|---|---|---|
| `CEDAR_LLM_PROVIDER` | `groq` | `groq` (Llama, default) or `anthropic` (Claude) |
| `GROQ_API_KEY` | — | Groq key ([free](https://console.groq.com)); without it, deterministic fallback |
| `CEDAR_MODEL` | `llama-3.3-70b-versatile` | Model id for the active provider |
| `CEDAR_MAX_TOKENS` | `512` | Cap on model output tokens |
| `CEDAR_LLM_GATE` | `1` | Skip the model on clear-HOLD cycles, during cooldown, and past budget |
| `CEDAR_LLM_DAILY_BUDGET` | `0` | Max model calls/day (`0` = unlimited) |

### Chain (reads & writes)
| Variable | Default | Purpose |
|---|---|---|
| `CEDAR_DATA_SOURCE` | `mock` | `mock` or `casper` (real MCP reads) |
| `CEDAR_SIGNER` | `mock` | `mock` (fabricated hashes) or `casper` (**real on-chain signing**) |
| `VAULT_ROUTER_HASH` | — | Deployed contract package hash |
| `CASPER_NODE_URL` | testnet public node | JSON-RPC endpoint |
| `CASPER_SECRET_KEY` / `CASPER_SECRET_KEY_B64` | — | Signing key path, or base64 (decoded to a file at startup for PaaS hosts) |
| `CASPER_CALL_PAYMENT` | `5000000000` | Motes per reallocate (5 CSPR) |

### Loop & storage
| Variable | Default | Purpose |
|---|---|---|
| `CEDAR_INTERVAL` | `120` | Seconds between cycles |
| `CEDAR_AUTOSTART` | `1` | Start the loop on boot |
| `CEDAR_ADMIN_TOKEN` | — | If set, write/control endpoints require it (`Authorization: Bearer` / `X-Admin-Token`); unset = open for local/demo |
| `DATABASE_URL` | — | Postgres (production); falls back to SQLite `CEDAR_DB` |

> ⚠️ **Single instance only.** The scheduler is an in-process thread — running 2 replicas means 2 agents both signing.

---

## API reference

Base URL: same origin as the dashboard (`https://trycedar.xyz`).

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/healthz` | Liveness + current mode (`data_source`, `signer`, `db`) |
| `GET`  | `/agent/status` | Current state + next-cycle countdown |
| `GET`  | `/agent/feed` | Recent cycle log (dashboard feed) |
| `GET`  | `/agent/portfolio` | Allocation across pools + total value |
| `GET`  | `/agent/guardrails` | Guardrail config + trigger counts + history |
| `GET`  | `/agent/audit` | Full paginated audit log |
| `GET` / `POST` | `/agent/policy` | Read / update the active policy |
| `POST` | `/agent/pause` · `/agent/resume` | Kill switch |
| `POST` | `/agent/onboard` | Initial policy + wallet connect |
| `POST` | `/agent/run-once` | Run a single cycle now |
| `POST` | `/agent/demo/{name}` | Seed a demo scenario (`spike` · `bad-data` · `divergence`) |

---

## Smart contract — `VaultRouter`

Minimal by design ([`contracts/vault_router/src/lib.rs`](contracts/vault_router/src/lib.rs)), written in **Odra** (Rust):

| Entrypoint | Access | Effect |
|---|---|---|
| `init()` | constructor | Installer becomes **owner** |
| `deposit(pool_id, amount)` | **owner-only** | Records allocation, emits `Deposited` |
| `reallocate(from_pool, to_pool, amount)` | **owner-only** | Moves allocation, emits `Reallocated` — *the transaction-producing action* |
| `get_allocation` · `get_total_value` · `get_owner` | view | Reads |

Pools are a fixed three-member enum (`PoolA/B/C`) matching the pre-vetted allow-list. Because entrypoints are owner-gated, **only the agent's key can actuate** — the contract enforces server-side signing as the sole write path.

**Live on Casper Testnet:** [`hash-dc100561…b1828135`](https://testnet.cspr.live/contract-package/dc10056192be60ae8db84e0b24e27629aec44381ba41b3bebfc89501b1828135) — full address record in **[DEPLOYMENT.md](DEPLOYMENT.md)**.

```bash
cd contracts/vault_router && cargo test     # native Odra MockVM tests
cargo install cargo-odra                     # build wasm + deploy
scripts/deploy_contract.sh
```

---

## Safety design (for reviewers)

| Concern | Where it lives |
|---|---|
| Bad-data guardrail | [`agent/nodes/validate.py`](agent/nodes/validate.py) |
| Grounded reasoning + code-side output guards | [`agent/nodes/reason.py`](agent/nodes/reason.py) |
| Deterministic recheck | [`agent/nodes/recheck.py`](agent/nodes/recheck.py) + [`agent/decision.py`](agent/decision.py) |
| Cooldown / position-cap / cost / anomaly | [`agent/nodes/guardrails.py`](agent/nodes/guardrails.py) |
| Every-path logging + provenance | [`agent/nodes/log.py`](agent/nodes/log.py) |
| On-chain state read-back | [`agent/chain_state.py`](agent/chain_state.py) |

**Data provenance is never silently dropped.** Single-source readings are surfaced as `UNVERIFIED` in the reasoning trace and the Guardrails UI. On-chain allocations are read from contract storage each cycle; an RPC failure falls back to cache *with a logged warning*, never silently.

---

## Cost controls

The LLM is consulted **only when capital might actually move**, protecting your API key:

1. **Clear-HOLD gate** — if the deterministic pre-check sees no actionable move, the model is skipped.
2. **Cooldown gate** — during an active cooldown a reallocation can't execute, so reasoning is skipped.
3. **Daily budget** — `CEDAR_LLM_DAILY_BUDGET` caps calls/day; once spent, the deterministic engine decides.

Plus `CEDAR_MAX_TOKENS`, JSON mode, and `temperature=0` for cheap, deterministic calls.

---

## Deployment

Single-service Docker image (FastAPI serves the built dashboard — one URL, no CORS). The image builds `casper-client` from source so real on-chain signing works in the cloud.

```bash
docker build -t cedar .
docker run -p 8000:8000 --env-file .env cedar
```

**Railway (recommended):** connect the repo, add a Postgres plugin, set the env vars (`CEDAR_SIGNER=casper`, `CASPER_SECRET_KEY_B64`, `GROQ_API_KEY`, …), deploy. Keep it at **one replica** — the scheduler is an in-process thread.

---

## Tech stack

| Layer | Technology |
|---|---|
| Agent orchestration | **LangGraph** `StateGraph` (typed `CycleState`) |
| Reasoning | **Groq** · Llama 3.3 70B (JSON mode) · Claude optional |
| Backend | **FastAPI** · in-process scheduler · **SQLAlchemy** (Postgres / SQLite) |
| Smart contract | **Odra** (Rust) on **Casper** · `casper-client` |
| Data | **CSPR.trade MCP** + **Casper MCP** (two-provider cross-check) |
| Frontend | **React 19** · **Vite** · TypeScript · **recharts** · light/dark theme |
| Deploy | **Docker** (single service) · **Railway** / Render / Fly |

---

## Project layout

```
contracts/vault_router/   Odra smart contract (deposit / reallocate / views) + tests
agent/
  graph.py                LangGraph StateGraph wiring the pipeline
  types.py                typed state, policy, snapshot, decision models
  decision.py             deterministic decision engine (recheck + fallback)
  config.py               env loading + PaaS secret materialization
  chain_state.py          on-chain allocation read-back (JSON-RPC)
  mcp_clients.py          Casper / CSPR.trade read adapters (mock + real)
  mcp_real.py             real MCP clients (CSPR.trade, cspr.cloud)
  cspr_click.py           server-side signer (mock + real casper-client)
  scheduler.py            fixed-interval loop runner with pause/resume
  nodes/                  observe · validate · reason · recheck · guardrails · actuate · log
api/
  main.py                 FastAPI control plane + serves the dashboard
  store.py                SQLAlchemy store (cycles, policy, allocations, run-state)
frontend/                 React + Vite dashboard, landing, and /docs
tests/                    per-segment test gates (43 Python)
scripts/                  deploy_contract.sh · seed_demo.py
```

---

## Roadmap

**Near term** — real token custody (escrowed CEP-18 balances behind the owner-gated model) · activate the two-provider price cross-check on mainnet-indexed tokens · policy learning (proposed to the human, never self-applied).

**Medium term** — multi-strategy support (LP fees + staking + lending) behind the pre-vetted allow-list · notification channel (webhook/Telegram) for EXECUTED/BLOCKED events.

**Positioning** — the pattern *(validated observation → grounded reasoning → deterministic recheck → named guardrails → every-path logging)* applies to any agent that touches real value.

---

## License

[MIT](LICENSE) © 2026 — original work built for the Casper Agentic Buildathon 2026.

---

<div align="center">

**[Live app](https://trycedar.xyz)** · **[Docs](https://trycedar.xyz/docs)** · Built for the Casper Agentic Buildathon 2026

</div>
