# Contributing to Cedar

Thanks for your interest! Cedar is an autonomous yield-routing agent on Casper built for the Casper Agentic Buildathon 2026.

## Getting started

```bash
git clone https://github.com/mrfomoweb3/Cedar.git && cd Cedar
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                      # all tests must pass
cp .env.example .env           # defaults run fully offline (mock mode)
uvicorn api.main:app --reload
```

Frontend: `cd frontend && npm install && npm run dev`.
Contract: `cd contracts/vault_router && cargo test` (needs the pinned nightly toolchain).

## Ground rules

- **Tests first-class:** every behavior change needs a test (`tests/`). Run `pytest -q` before pushing.
- **Safety pipeline is sacred:** changes to `agent/nodes/*` must not weaken a guardrail, the deterministic recheck, or every-path logging. PRs that bypass a veto layer will be declined.
- **No secrets in the repo:** `.env`, `*.pem`, `keys/`, `*.db` are gitignored — keep it that way. Never commit key material, even in tests (use synthetic fixtures).
- **Style:** match the surrounding code. Python is typed and terse; frontend is React 19 + TS with the existing token-based CSS.

## PR process

1. Fork / branch from `main`.
2. Keep PRs focused — one concern per PR.
3. Describe *what* and *why*; link an issue if one exists.
4. CI (tests + frontend build) must be green.
