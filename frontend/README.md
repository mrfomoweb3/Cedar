# Cedar Frontend

Dark-mode fintech-terminal dashboard for the Cedar autonomous yield-routing
agent. Vite + React + TypeScript + recharts; design tokens per the project spec
(JetBrains Mono numerics, no gradients, refusals rendered as prominently as
executions).

## Run

```bash
npm install
npm run dev        # http://localhost:5173
```

Expects the Cedar API on `http://localhost:8000` (override with
`VITE_API_BASE` in `.env`).

## Screens

| Route | Screen |
|---|---|
| `/` | Live Dashboard — reasoning feed (hero), allocation donut, guardrail status, kill switch |
| `/portfolio` | Positions + allocation-over-time stacked area chart |
| `/guardrails` | Data-provenance card, per-guardrail trigger counts, recheck agreement %, trigger history |
| `/audit` | Full cycle ledger — filter, search, CSV export, explorer-linked tx hashes |
| `/settings` | Live policy editing (explicit Save, applies next cycle) |
| `/onboarding` | 3-step setup wizard — the one deliberate human touchpoint |

The Dashboard's **Spike APY / Bad Data** buttons require the mock data source
(`CEDAR_DATA_SOURCE=mock` on the backend); in real-reads mode they return 400 by
design.
