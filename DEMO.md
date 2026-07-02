# Cedar — Demo Video Script (~3 minutes)

Target: show a judge, in one take, that Cedar **thinks and acts on its own** —
and refuses as visibly as it executes. Record at 1440×900, Dashboard open.

## Setup (before recording)

```bash
# Terminal 1 — backend in demo mode (mock data => seedable scenarios, real loop)
CEDAR_DB=data/demo_video.db CEDAR_DATA_SOURCE=mock CEDAR_SIGNER=mock \
  CEDAR_INTERVAL=30 uvicorn api.main:app --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

For the **real-chain beat** (beat 4), pre-record or switch to:
`CEDAR_DATA_SOURCE=casper CEDAR_SIGNER=casper CEDAR_CONFIRM_TX=1` — one cycle,
then open the tx hash on testnet.cspr.live.

## Beats

**Beat 1 — the pitch (0:00–0:25).** Dashboard idle. Say: *"Cedar is an autonomous
yield router on Casper. A human sets the policy once — after that there is no
confirm button between reasoning and an on-chain transaction. The entire pitch is
what you're about to watch: the agent deciding, checking itself, and refusing."*
Point at the status chip + next-cycle countdown ticking.

**Beat 2 — autonomous execution (0:25–1:10).** Click **Spike APY**, let the next
cycle fire (or Run Cycle). The feed renders: observed APYs → Claude's
reasoning trace → `✓ deterministic engine agrees` → 4 guardrails pass → green
EXECUTED card with tx hash. Expand the card and read one line of the trace aloud.
*"Nobody clicked approve."*

**Beat 3 — the refusal (1:10–1:50).** Click **Spike APY** again immediately. The
cooldown guardrail blocks it: amber card, `Guardrail Triggered — cooldown`.
Then click **Bad Data** → next cycle: red `VALIDATION FAILED — APY 9000% out of
bounds`. Say: *"A 9000% APY is bad data, not a jackpot. The agent refuses, and the
refusal is logged with the same prominence as a trade."*

**Beat 4 — it's real (1:50–2:25).** Cut to the real-mode cycle (or pre-recorded
clip): real CSPR.trade APYs in the feed, EXECUTED card → click the tx hash →
**testnet.cspr.live shows the live deploy**. Show DEPLOYMENT.md hashes match.
*"Real MCP data in, real Claude reasoning, real transaction out — owner-gated
on-chain, only the agent's key can actuate."*

**Beat 5 — the safety architecture (2:25–3:00).** Guardrails screen. Point to:
the amber **Data Provenance** card (*"when its second data source can't corroborate,
Cedar says so — single-source, unverified, never silently trusted"*), the recheck
agreement %, and the trigger-history table. Close on the Audit Log + CSV export.
*"Every decision, including every refusal, is permanently auditable. That's what
makes autonomy safe to grant."*

## Checklist before submitting the recording

- [ ] Both an EXECUTED (green) and a BLOCKED (amber) card visible in the feed
- [ ] Tx hash click-through resolves on testnet.cspr.live on camera
- [ ] Data Provenance card shown (single-source state on real reads)
- [ ] Kill switch (Pause Agent) visible top-right throughout
- [ ] No secrets/keys visible in any terminal shot
