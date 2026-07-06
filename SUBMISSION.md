# Cedar — Casper Agentic Buildathon 2026 Submission

**Cedar is an autonomous yield-routing agent that moves capital on Casper — and knows when to refuse.**
It observes DeFi pool yields, reasons over them with an LLM, and — with **no human in the loop** —
signs and submits real on-chain reallocations to an owner-gated smart contract. Every action clears a
defense-in-depth safety pipeline; every decision, including every refusal, is logged and auditable.

---

## Submission links

| Deliverable | Link |
|---|---|
| **Live app** | https://trycedar.xyz |
| **Documentation** | https://trycedar.xyz/docs |
| **X / socials** | https://x.com/trycedar |
| **Source repository** | https://github.com/mrfomoweb3/Cedar |
| **Deployed contract (explorer)** | https://testnet.cspr.live/contract-package/2e02730283fb38e9ef03699ac81cb93e7c1194237d06b1cde95b4c12ae7b298d |
| **Proof: on-chain reallocation (current contract)** | https://testnet.cspr.live/deploy/0b80e11e8bb6127930e259fde4767f9a2f7a7954e143cb49ef792c96b9194ac7 |
| **Demo video** | ⬜ _TODO: paste YouTube/Loom link_ |
| **License** | [MIT](LICENSE) ✅ |

---

## On-chain facts (verifiable)

| Item | Value |
|---|---|
| Network | Casper **Testnet** (`casper-test`, protocol 2.0.0) |
| Contract package hash | `hash-2e02730283fb38e9ef03699ac81cb93e7c1194237d06b1cde95b4c12ae7b298d` |
| Owner / agent account | `01559240ecf20a26702948f0a076e85a1c430e1eb20b6627045c5cf43411ddfea2` |
| Contract source | [contracts/vault_router/src/lib.rs](contracts/vault_router/src/lib.rs) (Odra, Rust) |
| Full address record | [DEPLOYMENT.md](DEPLOYMENT.md) |

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
