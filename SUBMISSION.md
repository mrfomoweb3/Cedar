# Cedar — Casper Agentic Buildathon 2026 Submission

**Cedar is the only agent on Casper that moves *real capital* under a mandate it can *prove* it obeyed.**
It custodies real CSPR in an owner-gated Odra vault, observes DeFi pool yields, reasons over them with an
LLM, and — with **no human in the loop** — signs and submits its own on-chain reallocations. Every action
clears a defense-in-depth safety pipeline where every link can veto the model; every decision, including
every refusal, is logged and auditable. Not a chatbot with a wallet — **accountable autonomy.**

---

## Submission links

| Deliverable | Link |
|---|---|
| **Live app** | https://trycedar.xyz |
| **Documentation** | https://trycedar.xyz/docs |
| **X / socials** | https://x.com/trycedar |
| **Source repository** | https://github.com/mrfomoweb3/Cedar |
| **Deployed contract (v3, real custody)** | https://testnet.cspr.live/contract-package/afdbf6c32a6f6a54ec5aff5ebd8dbd2a92f672cd60e089cf7cb50ed55bc71d7c |
| **Proof: real deposit (custody)** | https://testnet.cspr.live/transaction/d9be93020cdd8c3d599c74626430bb6c0e3c3284e61d37223efa825149d0dcf6 |
| **Proof: autonomous reallocate** | https://testnet.cspr.live/transaction/a453635090e1ab68ec360b98380a7ebc716f1aa40439f537bfdf5d7f4f0b67c0 |
| **Proof: real withdraw** | https://testnet.cspr.live/transaction/be652b91158607afc5501b689afae44e16b437db47ddea3f5537f273c8d2cd28 |
| **Demo video** | ⬜ _TODO: paste YouTube/Loom link_ |
| **License** | [MIT](LICENSE) ✅ |

---

## On-chain facts (verifiable)

| Item | Value |
|---|---|
| Network | Casper **Testnet** (`casper-test`, protocol 2.0.0) |
| Contract package hash (v3) | `hash-afdbf6c32a6f6a54ec5aff5ebd8dbd2a92f672cd60e089cf7cb50ed55bc71d7c` |
| Real custody | Vault holds real CSPR; `get_backing() == get_total_value()` invariant verified on-chain |
| Owner / agent account | `01559240ecf20a26702948f0a076e85a1c430e1eb20b6627045c5cf43411ddfea2` |
| Contract source | [contracts/vault_router/src/lib.rs](contracts/vault_router/src/lib.rs) (Odra, Rust) |
| Full address record + tx log | [DEPLOYMENT.md](DEPLOYMENT.md) |

---

## Verify the claims in 60 seconds

**It's genuinely autonomous (no confirm gate).** The loop signs directly after the safety checks pass —
there is no human approval step between decision and execution:
- Loop wiring: [agent/graph.py](agent/graph.py) — `observe → validate → reason → recheck → guardrails → actuate → log`
- The critical branch: [`_after_guardrails`](agent/graph.py) routes an all-pass straight to `actuate`
- Signing: [agent/nodes/actuate.py](agent/nodes/actuate.py) → `signer.reallocate(...)`
- The driver: [agent/scheduler.py](agent/scheduler.py) — a background thread runs a cycle every interval

**It refuses unsafe actions, and logs why.** Defense in depth, each layer able to veto:
- Bad-data guardrail: [agent/nodes/validate.py](agent/nodes/validate.py)
- Grounded reasoning + code-side output guards: [agent/nodes/reason.py](agent/nodes/reason.py)
- Independent deterministic recheck: [agent/nodes/recheck.py](agent/nodes/recheck.py)
- Named guardrails (cooldown · position cap · cost · anomaly): [agent/nodes/guardrails.py](agent/nodes/guardrails.py)
- Every-path logging: [agent/nodes/log.py](agent/nodes/log.py)

**Run it yourself (offline, no keys):**
```bash
pip install -r requirements.txt
pytest -q                                    # 43 passing
uvicorn api.main:app                          # http://localhost:8000
curl -X POST localhost:8000/agent/demo/spike     # → EXECUTED
curl -X POST localhost:8000/agent/demo/bad-data  # → VALIDATION_FAILED (refusal)
curl      localhost:8000/agent/feed              # the reasoning + refusal log
```

---

## Deliverables checklist

- [x] Working, open-source code — builds, 43 tests passing
- [x] Genuine autonomous observe→reason→act loop, no human confirm gate
- [x] On-chain integration — owner-gated Odra `VaultRouter`, deployed + a real reallocate tx
- [x] Defense-in-depth safety pipeline with logged refusals
- [x] Live deployment — https://trycedar.xyz
- [x] README + architecture docs + `/docs` page
- [x] Deployed contract address published
- [x] Open-source license — [MIT](LICENSE)
- [ ] **Demo video** — _recording in progress_

---

## Tech stack

LangGraph · Groq (Llama 3.3 70B) · FastAPI · SQLAlchemy (Postgres/SQLite) · Odra (Rust) on Casper ·
`casper-client` · React + Vite · Docker · Railway.

Built for the **Casper Agentic Buildathon 2026**.
