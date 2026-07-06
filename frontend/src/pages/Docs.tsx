import { Link } from 'react-router-dom';
import mark from '../assets/cedar-mark.png';
import { ThemeToggle } from '../components/ThemeToggle';
import '../docs.css';

const CONTRACT = '2e02730283fb38e9ef03699ac81cb93e7c1194237d06b1cde95b4c12ae7b298d';
const EXPLORER = `https://testnet.cspr.live/contract-package/${CONTRACT}`;

const PIPELINE = [
  { n: '01', k: 'OBSERVE', s: 'Read APY + on-chain allocation + gas into a typed snapshot.' },
  { n: '02', k: 'VALIDATE', s: 'Range / staleness / cross-source checks. Bad data → halt.' },
  { n: '03', k: 'REASON', s: 'LLM over validated data only. Output hard-checked in code.' },
  { n: '04', k: 'RECHECK', s: 'Deterministic re-derivation. Disagree → HOLD.' },
  { n: '05', k: 'GUARDRAILS', s: 'Cooldown · cap · cost · anomaly. First fail blocks.' },
  { n: '06', k: 'ACTUATE', s: 'Sign + submit reallocate deploy. Capture tx hash.' },
];

const STEPS = [
  { k: 'OBSERVE', d: 'Pulls per-pool APY, the current on-chain allocation, and a gas estimate into a typed MarketSnapshot. Allocations are read directly from the deployed contract’s storage — the agent acts on chain truth, not a local cache.', fail: null },
  { k: 'VALIDATE', d: 'The bad-data guardrail. Range-checks APYs (a 9000% reading is bad data, not a jackpot), rejects stale snapshots, and halts on cross-source divergence rather than averaging two disagreeing providers.', fail: 'VALIDATION_FAILED' },
  { k: 'REASON', d: 'A schema-constrained LLM call (Llama 3.3 on Groq) that sees only the validated snapshot + active policy — it cannot browse, recall, or invent. Its JSON output is then hard-checked in code: unknown pools, over-cap amounts, and fabricated figures all force a HOLD.', fail: 'force-HOLD' },
  { k: 'RECHECK', d: 'A deterministic, non-LLM engine re-derives the same decision from the same data. If the dumb rule and the model disagree, Cedar force-HOLDs. This is the last line of defense against a confident-but-wrong model.', fail: 'force-HOLD' },
  { k: 'GUARDRAILS', d: 'Four named checks run in order — cooldown, position cap, cost-vs-gain, and a final anomaly recheck. The first failure short-circuits to a logged, named refusal.', fail: 'BLOCKED' },
  { k: 'ACTUATE', d: 'Only if everything passes: signs and submits the reallocate deploy with the agent’s own key via casper-client, and captures the real tx hash. Failures are surfaced, never silently retried — no double-spend.', fail: 'EXECUTION_FAILED' },
  { k: 'LOG', d: 'One record per cycle — on every path, action or refusal — powers both the live dashboard feed and the audit log, each with full data provenance.', fail: null },
];

const FEATURES = [
  { i: '🧠', t: 'Grounded reasoning', d: 'The model sees only validated data. Every figure it cites is matched against the snapshot; invent a number and it’s force-HELD — in code, not a prompt.' },
  { i: '🔁', t: 'Independent recheck', d: 'A deterministic engine recomputes each decision. Model and rule must agree, or the agent refuses.' },
  { i: '🛡️', t: 'Named guardrails', d: 'Cooldown, position cap, cost check, anomaly breaker — each refusal is logged with the exact guardrail that fired.' },
  { i: '🔎', t: 'Honest provenance', d: 'Single-source data is surfaced as UNVERIFIED, never silently trusted. The agent tells you when it’s flying with one eye.' },
  { i: '⛓️', t: 'Real on-chain actuation', d: 'Server-side signing submits a real reallocate deploy to an owner-gated Odra contract on Casper Testnet — verifiable on the explorer.' },
  { i: '💸', t: 'Cost-guarded', d: 'The LLM is called only when capital might move — skipped on clear holds, during cooldown, and past a daily budget.' },
  { i: '📜', t: 'Every-path audit log', d: 'One durable record per cycle powers the live feed and a full paginated audit trail. Nothing is hidden.' },
  { i: '⏸️', t: 'Kill switch', d: 'Pause and resume the autonomous loop at any time from the dashboard or the API.' },
];

const GUARDRAILS = [
  ['cooldown', 'Enforces the minimum time between two reallocations.'],
  ['position_cap', 'No single cycle may move more than max_reallocation_pct of total value.'],
  ['cost_check', 'Weighs gas + slippage against the APY gain over the hold horizon.'],
  ['anomaly_recheck', 'Final sanity pass on the proposed move before signing.'],
];

const API = [
  ['GET', '/healthz', 'Liveness + current mode (data_source, signer, db)'],
  ['GET', '/agent/status', 'Current state + next-cycle countdown'],
  ['GET', '/agent/feed', 'Recent cycle log (dashboard feed)'],
  ['GET', '/agent/portfolio', 'Allocation across pools + total value'],
  ['GET', '/agent/guardrails', 'Guardrail config + trigger counts + history'],
  ['GET', '/agent/audit', 'Full paginated audit log'],
  ['GET/POST', '/agent/policy', 'Read / update the active policy'],
  ['POST', '/agent/pause · /resume', 'Kill switch'],
  ['POST', '/agent/run-once', 'Run a single cycle now'],
  ['POST', '/agent/demo/{name}', 'Seed a demo scenario (spike · bad-data · divergence)'],
];

const TOC = [
  ['overview', 'Overview'],
  ['loop', 'The autonomous loop'],
  ['steps', 'Pipeline, step by step'],
  ['architecture', 'Architecture'],
  ['features', 'Features'],
  ['reasoning', 'Reasoning & data'],
  ['guardrails', 'Guardrails'],
  ['contract', 'Smart contract'],
  ['api', 'API reference'],
  ['deploy', 'Deployment'],
  ['stack', 'Tech stack'],
];

export function Docs() {
  return (
    <div className="docs">
      <header className="docs-nav">
        <Link to="/" className="docs-brand"><img src={mark} alt="" aria-hidden="true" /> Cedar Docs</Link>
        <div className="docs-nav-right">
          <a className="docs-nav-link" href={EXPLORER} target="_blank" rel="noreferrer">Contract ↗</a>
          <Link className="docs-nav-link" to="/app">Open app →</Link>
          <ThemeToggle />
        </div>
      </header>

      <div className="docs-shell">
        <nav className="docs-toc">
          <div className="docs-toc-title">On this page</div>
          {TOC.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
        </nav>

        <main className="docs-main">
          {/* hero */}
          <div className="docs-hero">
            <div className="docs-eyebrow">Documentation</div>
            <h1 className="docs-h1">How Cedar works</h1>
            <p className="docs-lede">
              Cedar is an autonomous agent that observes DeFi yields on Casper, reasons over them with
              an LLM, and signs its own on-chain reallocations — with a defense-in-depth safety
              pipeline where every link can veto the model. This page walks the full system end to end.
            </p>
            <div className="docs-badges">
              <span className="docs-badge">Network <b>Casper Testnet</b></span>
              <span className="docs-badge">Reasoning <b>Groq · Llama 3.3</b></span>
              <span className="docs-badge">Contract <b>Odra · Rust</b></span>
              <span className="docs-badge">Actuation <b>Server-side signing</b></span>
            </div>
          </div>

          {/* overview */}
          <section id="overview" className="docs-section">
            <h2>Overview</h2>
            <p>
              The core thesis: <b>an autonomous agent that touches money is only as good as the things it
              refuses to do.</b> Most agent demos are a single LLM call wired straight to an action. Cedar is
              the opposite — the LLM is one link in a chain where <b>every other link can veto it</b>.
            </p>
            <p>
              Bad market data is rejected before the model ever sees it. The model sees only a validated
              snapshot. Its output is hard-checked in code. A deterministic engine independently re-derives
              the decision. Named guardrails each get a final veto. And every path — action or refusal — is
              logged with full data provenance. The durable asset isn’t the yield router; it’s the safety
              pipeline.
            </p>
            <div className="docs-callout">
              <b>No confirm button.</b> There is no human clicking “yes” between reasoning and actuation.
              Safety comes from the pipeline, not from a person in the way.
            </div>
          </section>

          {/* loop diagram */}
          <section id="loop" className="docs-section">
            <h2>The autonomous loop</h2>
            <p className="docs-lead-sub">Each cycle runs end to end and either acts or refuses — always logged.</p>
            <div className="docs-pipeline">
              {PIPELINE.map((p) => (
                <div className="docs-pstep" key={p.k}>
                  <div className="docs-pnum">{p.n}</div>
                  <div className="docs-pname">{p.k}</div>
                  <div className="docs-psub">{p.s}</div>
                </div>
              ))}
            </div>
            <div className="docs-plog"><b>LOG</b> — one record per cycle (every path) → live feed + audit log</div>
          </section>

          {/* steps */}
          <section id="steps" className="docs-section">
            <h2>Pipeline, step by step</h2>
            <div className="docs-steps">
              {STEPS.map((s, i) => (
                <div className="docs-step" key={s.k}>
                  <div className="docs-step-n">{i < 6 ? String(i + 1).padStart(2, '0') : '✓'}</div>
                  <div>
                    <div className="docs-step-k">{s.k}</div>
                    <div className="docs-step-d">{s.d}</div>
                    {s.fail && <span className="docs-step-fail">on failure → {s.fail}</span>}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* architecture */}
          <section id="architecture" className="docs-section">
            <h2>Architecture</h2>
            <p>
              The agent graph depends only on two protocols — a <b>MarketDataSource</b> (read) and a{' '}
              <b>Signer</b> (write). Mock implementations drive dev, tests, and the offline demo; the Casper
              implementations wire the real chain. You switch between them with two environment variables and
              nothing else changes.
            </p>
            <div className="docs-arch">
              <div className="docs-layer">
                <div className="docs-layer-t">Browser · trycedar.xyz</div>
                <div className="docs-layer-row">
                  <span className="docs-chip">React 19 + Vite SPA</span>
                  <span className="docs-chip">/ landing</span>
                  <span className="docs-chip">/app dashboard</span>
                  <span className="docs-chip">/docs</span>
                </div>
              </div>
              <div className="docs-arch-arrow">↓ same-origin HTTPS (JSON)</div>
              <div className="docs-layer">
                <div className="docs-layer-t">Control plane · FastAPI (api/main.py)</div>
                <div className="docs-layer-row">
                  <span className="docs-chip">REST endpoints</span>
                  <span className="docs-chip">in-process scheduler</span>
                  <span className="docs-chip">serves the dashboard</span>
                  <span className="docs-chip">SQLAlchemy store</span>
                </div>
              </div>
              <div className="docs-arch-arrow">↓ LangGraph StateGraph</div>
              <div className="docs-layer">
                <div className="docs-layer-t">Agent · observe → validate → reason → recheck → guardrails → actuate → log</div>
                <div className="docs-layer-row">
                  <span className="docs-chip">MarketDataSource → CSPR.trade + Casper MCP</span>
                  <span className="docs-chip">Signer → casper-client</span>
                </div>
              </div>
              <div className="docs-arch-arrow">↓ JSON-RPC</div>
              <div className="docs-layer">
                <div className="docs-layer-t">Casper Testnet</div>
                <div className="docs-layer-row">
                  <span className="docs-chip">Odra VaultRouter (owner-gated)</span>
                </div>
              </div>
            </div>
          </section>

          {/* features */}
          <section id="features" className="docs-section">
            <h2>Features</h2>
            <div className="docs-features">
              {FEATURES.map((f) => (
                <div className="docs-feature" key={f.t}>
                  <div className="docs-feature-ico">{f.i}</div>
                  <div className="docs-feature-t">{f.t}</div>
                  <div className="docs-feature-d">{f.d}</div>
                </div>
              ))}
            </div>
          </section>

          {/* reasoning */}
          <section id="reasoning" className="docs-section">
            <h2>Reasoning &amp; data</h2>
            <h3>The model</h3>
            <p>
              REASON is a schema-constrained call to <b>Llama 3.3 70B on Groq</b> (JSON mode, temperature 0).
              It receives only the validated snapshot and the active policy. Claude is available as an
              alternate provider. With no API key configured, the node transparently falls back to the
              deterministic engine, so the whole loop still runs offline.
            </p>
            <h3>Two-provider data</h3>
            <p>
              OBSERVE reads from the <b>CSPR.trade MCP</b> (deriving fee APR from real reserves + swap volume)
              and cross-checks against the <b>Casper MCP</b> (cspr.cloud). When a reading isn’t corroborated
              by a second provider it is surfaced as <b>UNVERIFIED</b> in the reasoning trace and the
              Guardrails UI — never silently trusted.
            </p>
            <h3>Cost controls</h3>
            <p>The LLM is consulted only when capital might actually move, protecting your API key:</p>
            <div className="docs-tablewrap">
              <table className="docs-table">
                <thead><tr><th>Gate</th><th>Behaviour</th></tr></thead>
                <tbody>
                  <tr><td>Clear-HOLD gate</td><td>If the deterministic pre-check sees no actionable move, the model is skipped.</td></tr>
                  <tr><td>Cooldown gate</td><td>During an active cooldown a reallocation can’t execute, so reasoning is skipped.</td></tr>
                  <tr><td>Daily budget</td><td><span className="docs-code">CEDAR_LLM_DAILY_BUDGET</span> caps calls/day; once spent, the deterministic engine decides.</td></tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* guardrails */}
          <section id="guardrails" className="docs-section">
            <h2>Guardrails</h2>
            <p>After the recheck agrees, four named guardrails run in order. The first to fail short-circuits
              the cycle to a <span className="docs-pill block">BLOCKED</span> outcome, logged with the exact
              guardrail that fired.</p>
            <div className="docs-tablewrap">
              <table className="docs-table">
                <thead><tr><th>Guardrail</th><th>What it enforces</th></tr></thead>
                <tbody>
                  {GUARDRAILS.map(([n, d]) => (
                    <tr key={n}><td><code>{n}</code></td><td>{d}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3>Cycle outcomes</h3>
            <div className="docs-tablewrap">
              <table className="docs-table">
                <thead><tr><th>Outcome</th><th>Meaning</th></tr></thead>
                <tbody>
                  <tr><td><span className="docs-pill exec">EXECUTED</span></td><td>Reallocation signed and submitted on-chain.</td></tr>
                  <tr><td><span className="docs-pill block">BLOCKED</span></td><td>A guardrail or the recheck vetoed the move.</td></tr>
                  <tr><td>HOLD</td><td>The agent decided to hold — no move warranted.</td></tr>
                  <tr><td><span className="docs-pill fail">VALIDATION_FAILED</span></td><td>Bad or divergent input data — halted before reasoning.</td></tr>
                  <tr><td><span className="docs-pill fail">EXECUTION_FAILED</span></td><td>The on-chain submission failed — surfaced, never retried silently.</td></tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* contract */}
          <section id="contract" className="docs-section">
            <h2>Smart contract — VaultRouter</h2>
            <p>
              A minimal <b>Odra</b> (Rust) contract on Casper Testnet. Every state-changing entrypoint is{' '}
              <b>owner-only</b>, so only the agent’s key can actuate — the contract itself enforces
              server-side signing as the sole write path.
            </p>
            <div className="docs-tablewrap">
              <table className="docs-table">
                <thead><tr><th>Entrypoint</th><th>Access</th><th>Effect</th></tr></thead>
                <tbody>
                  <tr><td><code>init()</code></td><td>constructor</td><td>Installer becomes owner</td></tr>
                  <tr><td><code>deposit(pool, amount)</code></td><td>owner-only</td><td>Records allocation, emits Deposited</td></tr>
                  <tr><td><code>reallocate(from, to, amount)</code></td><td>owner-only</td><td>Moves allocation, emits Reallocated</td></tr>
                  <tr><td><code>get_allocation / get_total_value / get_owner</code></td><td>view</td><td>Reads</td></tr>
                </tbody>
              </table>
            </div>
            <p style={{ marginTop: 16 }}>
              Live: <a href={EXPLORER} target="_blank" rel="noreferrer" className="docs-code">hash-dc100561…b1828135 ↗</a>
            </p>
          </section>

          {/* api */}
          <section id="api" className="docs-section">
            <h2>API reference</h2>
            <p className="docs-lead-sub">Base URL is the same origin as the dashboard.</p>
            <div className="docs-tablewrap">
              <table className="docs-table">
                <thead><tr><th>Method</th><th>Path</th><th>Purpose</th></tr></thead>
                <tbody>
                  {API.map(([m, p, d]) => (
                    <tr key={p}><td><code>{m}</code></td><td><code>{p}</code></td><td>{d}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* deploy */}
          <section id="deploy" className="docs-section">
            <h2>Deployment</h2>
            <p>
              Cedar ships as a single Docker image — FastAPI serves the built dashboard, so it’s one URL with
              no CORS. The image builds <span className="docs-code">casper-client</span> from source so real
              on-chain signing works in the cloud.
            </p>
            <pre className="docs-pre">
{`docker build -t cedar .
docker run -p 8000:8000 --env-file .env cedar`}
            </pre>
            <p>
              <b>Railway (recommended):</b> connect the repo, add a Postgres plugin, set the env vars
              (<span className="docs-code">CEDAR_SIGNER=casper</span>, <span className="docs-code">CASPER_SECRET_KEY_B64</span>,{' '}
              <span className="docs-code">GROQ_API_KEY</span>, …), and deploy at a single replica.
            </p>
            <div className="docs-callout">
              <b>Single instance only.</b> The scheduler is an in-process thread — two replicas means two
              agents both signing. Never scale past one.
            </div>
          </section>

          {/* stack */}
          <section id="stack" className="docs-section">
            <h2>Tech stack</h2>
            <div className="docs-arch">
              <div className="docs-layer">
                <div className="docs-layer-row">
                  <span className="docs-chip">LangGraph</span>
                  <span className="docs-chip">Groq · Llama 3.3 70B</span>
                  <span className="docs-chip">FastAPI</span>
                  <span className="docs-chip">SQLAlchemy · Postgres / SQLite</span>
                  <span className="docs-chip">Odra (Rust)</span>
                  <span className="docs-chip">casper-client</span>
                  <span className="docs-chip">React 19</span>
                  <span className="docs-chip">Vite</span>
                  <span className="docs-chip">recharts</span>
                  <span className="docs-chip">Docker</span>
                  <span className="docs-chip">Railway</span>
                </div>
              </div>
            </div>
          </section>

          <footer className="docs-footer">
            <span>Built for the Casper Agentic Buildathon 2026</span>
            <Link to="/app" className="docs-nav-link">Open the live agent →</Link>
          </footer>
        </main>
      </div>
    </div>
  );
}
