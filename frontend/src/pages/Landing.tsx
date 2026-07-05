import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import mark from '../assets/cedar-mark.png';
import { ThemeToggle } from '../components/ThemeToggle';
import '../landing.css';

const CONTRACT = 'dc10056192be60ae8db84e0b24e27629aec44381ba41b3bebfc89501b1828135';
const EXPLORER = `https://testnet.cspr.live/contract-package/${CONTRACT}`;

const LOOP = [
  { k: 'OBSERVE', d: 'Pull live pool yields + on-chain state from Casper MCP and CSPR.trade.' },
  { k: 'VALIDATE', d: 'Reject bad data — range, staleness, and cross-provider divergence.' },
  { k: 'REASON', d: 'An LLM (Llama 3.3 on Groq) decides HOLD or REALLOCATE over only the validated snapshot.' },
  { k: 'RECHECK', d: 'A deterministic, non-LLM engine re-derives the call. Disagree → HOLD.' },
  { k: 'GUARDRAILS', d: 'Cooldown, position cap, cost-vs-gain, anomaly. First fail short-circuits.' },
  { k: 'ACTUATE', d: 'Sign + submit the reallocation on Casper. Capture the tx hash.' },
];

const SAFETY = [
  { t: 'Fabrication check', d: 'Every figure the model cites is matched against the validated snapshot. Invent a number, get force-HELD — in code, not a prompt.' },
  { t: 'Independent recheck', d: 'A dumb, deterministic rule recomputes the decision. If it and the model disagree, the agent refuses. Last line of defense.' },
  { t: 'Named guardrails', d: 'Cooldown, position cap, cost check, anomaly breaker — each refusal is logged with the exact guardrail that fired.' },
  { t: 'Honest provenance', d: 'Single-source data is surfaced as UNVERIFIED, never silently trusted. The agent tells you when it is flying with one eye.' },
];

// soft, harmonious card tints derived from the brand hues (green/amber/slate)
const LOOP_COLORS = [
  { bg: '#EAF3EC', fg: '#1A5C2E' }, // forest green
  { bg: '#FAF2E7', fg: '#B4763A' }, // warm sand / amber
  { bg: '#ECF1F6', fg: '#3E6D8E' }, // slate blue
  { bg: '#F7EFE9', fg: '#BC6A4A' }, // terracotta
  { bg: '#EDF3E9', fg: '#5E7A45' }, // sage / olive
  { bg: '#EFF1F4', fg: '#55617A' }, // cool gray
];

export function Landing() {
  const [cycles, setCycles] = useState<number | null>(null);
  const [blocks, setBlocks] = useState<number | null>(null);

  useEffect(() => {
    api.status().then((s) => setCycles(s.total_cycles)).catch(() => {});
    api.guardrails()
      .then((g) => setBlocks(Object.values(g.trigger_counts).reduce((a, b) => a + b, 0)))
      .catch(() => {});
  }, []);

  return (
    <div className="lp">
      {/* nav */}
      <header className="lp-nav">
        <div className="lp-brand"><img src={mark} className="brand-mark-img" alt="" aria-hidden="true" /> Cedar</div>
        <nav className="lp-nav-links">
          <a href="#loop">How it works</a>
          <a href="#safety">Safety</a>
          <a href="#proof">Live proof</a>
          <a href="#roadmap">Roadmap</a>
          <Link to="/docs">Docs</Link>
        </nav>
        <div className="flex gap" style={{ justifySelf: 'end', gap: 10 }}>
          <ThemeToggle />
          <Link to="/app" className="lp-btn lp-btn-primary">Launch App →</Link>
        </div>
      </header>

      {/* hero */}
      <section className="lp-hero">
        <div className="lp-grid-bg" />
        <h1 className="lp-h1">
          Autonomous capital movement,<br />with a built-in <span className="lp-grad">“no.”</span>
        </h1>
        <p className="lp-sub">
          Cedar watches Casper yields and signs its own reallocations, no human in the loop.
          Every action clears a safety pipeline; every refusal is logged.
        </p>
        <div className="lp-cta-row">
          <Link to="/app" className="lp-btn lp-btn-primary lp-btn-lg">Launch the live agent →</Link>
          <a href={EXPLORER} target="_blank" rel="noreferrer" className="lp-btn lp-btn-ghost lp-btn-lg">
            View contract on testnet ↗
          </a>
        </div>
        <div className="lp-proofcards">
          <div className="lp-pc"><div className="lp-pc-n green">{cycles ?? '—'}</div><div className="lp-pc-l">autonomous cycles run</div></div>
          <div className="lp-pc"><div className="lp-pc-n">{blocks ?? '—'}</div><div className="lp-pc-l">unsafe moves blocked</div></div>
          <div className="lp-pc"><div className="lp-pc-n">0</div><div className="lp-pc-l">human confirmations</div></div>
        </div>
      </section>

      {/* brand marquee — real logo + wordmark, repeating */}
      <div className="lp-marquee" aria-label="Cedar">
        <div className="lp-marquee-track">
          {Array.from({ length: 16 }).map((_, i) => (
            <span className="lp-marquee-item" key={i}>
              <img src={mark} className="lp-marquee-mark" alt="" aria-hidden="true" />
              <span className="lp-marquee-word">Cedar</span>
              <span className="lp-marquee-dot" aria-hidden="true" />
            </span>
          ))}
        </div>
      </div>

      {/* loop */}
      <section id="loop" className="lp-section">
        <div className="lp-eyebrow">The autonomous loop</div>
        <h2 className="lp-h2">Six steps. No confirm button.</h2>
        <p className="lp-lead">
          Safety comes from the pipeline, not from a human in the way. Each cycle runs
          end to end and either acts or refuses — always logged.
        </p>
        <div className="lp-stack">
          {LOOP.map((s, i) => {
            const c = LOOP_COLORS[i % LOOP_COLORS.length];
            return (
              <div className="lp-stack-card" key={s.k}
                style={{ top: `${104 + i * 16}px`, zIndex: i + 1, background: c.bg }}>
                <div className="lp-stack-top">
                  <div className="lp-stack-i" style={{ color: c.fg }}>{String(i + 1).padStart(2, '0')}</div>
                  <div className="lp-stack-step">Step {i + 1} / {LOOP.length}</div>
                </div>
                <div>
                  <div className="lp-stack-k" style={{ color: c.fg }}>{s.k}</div>
                  <div className="lp-stack-d">{s.d}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* safety */}
      <section id="safety" className="lp-section lp-section-alt">
        <div className="lp-eyebrow">The differentiator</div>
        <h2 className="lp-h2">An agent that touches money is only as<br />good as the things it refuses to do.</h2>
        <div className="lp-grid2">
          {SAFETY.map((c) => (
            <div className="lp-card" key={c.t}>
              <div className="lp-card-t">{c.t}</div>
              <div className="lp-card-d">{c.d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* live proof */}
      <section id="proof" className="lp-section lp-center">
        <div className="lp-eyebrow">Not a mock</div>
        <h2 className="lp-h2">Real reasoning. Real transactions.</h2>
        <p className="lp-lead">
          The loop reads live market data, reasons with an LLM, and submits real deploys
          to a deployed Odra contract on Casper Testnet — verifiable on the explorer.
        </p>
        <div className="lp-proof">
          <div className="lp-proof-row"><span className="lp-proof-k">Contract (owner-gated)</span>
            <a href={EXPLORER} target="_blank" rel="noreferrer" className="mono lp-link">{CONTRACT.slice(0, 10)}…{CONTRACT.slice(-6)} ↗</a></div>
          <div className="lp-proof-row"><span className="lp-proof-k">Autonomous reallocation</span>
            <a href="https://testnet.cspr.live/deploy/ef454d281d2605ea8610a3662fd791b218921cc6d1f7932cceea63588001cd60" target="_blank" rel="noreferrer" className="mono lp-link">ef454d28…cd60 ↗</a></div>
          <div className="lp-proof-row"><span className="lp-proof-k">Refusal on real data</span>
            <span className="mono" style={{ color: 'var(--blocked)' }}>recheck disagreement → HOLD</span></div>
        </div>
        <div style={{ marginTop: 28 }}>
          <Link to="/app" className="lp-btn lp-btn-primary lp-btn-lg">Watch it decide, live →</Link>
        </div>
      </section>

      {/* roadmap */}
      <section id="roadmap" className="lp-section lp-section-alt">
        <div className="lp-eyebrow">What's next</div>
        <h2 className="lp-h2">Roadmap</h2>
        <div className="lp-road">
          <div className="lp-road-col">
            <div className="lp-road-when">Now — Qualification</div>
            <ul>
              <li>Autonomous loop live on Casper Testnet</li>
              <li>Owner-gated VaultRouter, on-chain state read-back</li>
              <li>LLM reasoning + deterministic recheck + guardrails</li>
              <li>Two-provider data cross-check with honest provenance</li>
            </ul>
          </div>
          <div className="lp-road-col">
            <div className="lp-road-when">Next</div>
            <ul>
              <li>Real vault custody (escrowed token positions, not records)</li>
              <li>Mainnet pools + live fee/price cross-verification</li>
              <li>Policy marketplace — shareable, auditable mandates</li>
              <li>Multi-strategy agents under one risk budget</li>
            </ul>
          </div>
          <div className="lp-road-col">
            <div className="lp-road-when">Vision</div>
            <ul>
              <li>Auditable autonomy as a primitive for on-chain agents</li>
              <li>Every decision — and refusal — provable and replayable</li>
              <li>Human sets the mandate once; the agent earns the trust</li>
            </ul>
          </div>
        </div>
      </section>

      {/* cta band */}
      <section className="lp-band lp-center">
        <h2 className="lp-h2" style={{ marginBottom: 12 }}>See an agent you can actually trust.</h2>
        <p className="lp-lead" style={{ marginBottom: 24 }}>A human sets the goal, then steps back.</p>
        <Link to="/app" className="lp-btn lp-btn-primary lp-btn-lg">Launch Cedar →</Link>
      </section>

      <footer className="lp-footer">
        <div className="lp-brand"><img src={mark} className="brand-mark-img" alt="" aria-hidden="true" /> Cedar</div>
        <div className="lp-foot-note">
          <span className="chip testnet">CASPER TESTNET</span>
          <span className="muted">Built for the Casper Agentic Buildathon 2026</span>
        </div>
      </footer>
    </div>
  );
}
