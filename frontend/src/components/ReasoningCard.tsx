import { useState } from 'react';
import type { Cycle } from '../api';
import { fmtNum, fmtTime, outcomeLabel, outcomeVariant, plainReasoning, truncHash } from '../format';
import { Copy } from './Copy';

const STATE_DOT: Record<string, string> = {
  executed: 's-live', blocked: 's-blocked', hold: 's-hold', failed: 's-error',
};

export function ReasoningCard({ cycle, defaultOpen = false }: { cycle: Cycle; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const variant = outcomeVariant(cycle.outcome);
  const pools = cycle.snapshot?.pools ?? {};
  const verifiedMap = cycle.snapshot?.cross_source_verified;
  const singleSource = verifiedMap
    ? Object.values(verifiedMap).every((v) => !v)
    : false;

  // one-line summary shown while collapsed, so a card is scannable at a glance
  const summary = cycle.action === 'REALLOCATE' && cycle.from_pool
    ? `${fmtNum(cycle.amount)} ${cycle.from_pool} → ${cycle.to_pool}`
    : (cycle.action === 'HOLD' ? 'Hold — no move' : (cycle.hold_reason ? cycle.hold_reason : '—'));

  return (
    <div className={`rcard ${variant} ${open ? 'open' : ''}`}>
      <div className="rcard-head" onClick={() => setOpen((o) => !o)}
        role="button" aria-expanded={open}>
        <div className={`rcard-title ${STATE_DOT[variant]}`}>
          <span className="dot" />
          {outcomeLabel(cycle.outcome)}
          <span className={`tag ${variant}`} style={{ marginLeft: 6 }}>{cycle.outcome}</span>
          {singleSource && (
            <span className="tag blocked" title="Readings not corroborated by a second data provider">
              single-source · unverified
            </span>
          )}
          {!open && <span className="rcard-summary">{summary}</span>}
        </div>
        <div className="rcard-meta">
          <span className="rcard-time">{fmtTime(cycle.finished_at ?? cycle.started_at)}</span>
          <span className="rcard-chev" aria-hidden="true">▾</span>
        </div>
      </div>

      {open && (
        <div className="rcard-body">
          {Object.keys(pools).length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div className="rrow"><span className="k">Observed:</span></div>
              {Object.values(pools).map((p) => (
                <div className="rrow" key={p.pool_id}>
                  <span className="k" style={{ marginLeft: 12 }}>{p.pool_id}</span>
                  <span className="v">→ {fmtNum(p.apy)}% APY</span>
                  <span className="muted">alloc {fmtNum(p.allocation)} · {p.source}</span>
                </div>
              ))}
              <div className="rrow">
                <span className="k" style={{ marginLeft: 12 }}>Gas est.</span>
                <span className="v">→ {fmtNum(cycle.snapshot?.gas_estimate, 3)} CSPR</span>
              </div>
            </div>
          )}

          <hr className="section-divider" />

          <div className="rrow">
            <span className="k">Decision:</span>
            <span className="v">{cycle.action ?? '—'}
              {cycle.action === 'REALLOCATE' && cycle.from_pool &&
                ` ${fmtNum(cycle.amount)} ${cycle.from_pool} → ${cycle.to_pool}`}
            </span>
          </div>

          {cycle.reasoning && (
            <div className="rrow" style={{ marginTop: 4 }}>
              <span className="k">Rationale:</span>
              <span className="v" style={{ color: 'var(--text-2)' }}>{plainReasoning(cycle.reasoning)}</span>
            </div>
          )}
          <div className="rrow" style={{ marginTop: 4 }}>
            <span className="k">Recheck:</span>
            <span className="v">
              {cycle.recheck_agrees
                ? <span className="s-live">✓ deterministic engine agrees</span>
                : <span className="s-error">✗ disagreement — forced HOLD</span>}
            </span>
          </div>
          {cycle.guardrails.length > 0 && (
            <div style={{ marginTop: 4 }}>
              {cycle.guardrails.map((g) => (
                <div className="rrow" key={g.name}>
                  <span className="k">{g.name}:</span>
                  <span className="v">
                    {g.passed ? <span className="s-live">✓</span> : <span className="s-blocked">✗</span>} {g.detail}
                  </span>
                </div>
              ))}
            </div>
          )}

          {cycle.outcome === 'BLOCKED' && cycle.hold_reason && (
            <div style={{ marginTop: 8 }}>
              <span className="tag blocked">Guardrail Triggered</span>{' '}
              <span className="muted">{cycle.hold_reason}</span>
            </div>
          )}
          {(cycle.outcome === 'VALIDATION_FAILED' || cycle.outcome === 'EXECUTION_FAILED') && (
            <div style={{ marginTop: 8 }}>
              <span className="tag failed">Halted</span>{' '}
              <span className="muted">{cycle.hold_reason}</span>
            </div>
          )}

          {cycle.tx_hash && (
            <div style={{ marginTop: 8 }} className="rrow">
              <span className="k">Tx:</span>
              <a className="txhash" href={cycle.explorer_url} target="_blank" rel="noreferrer"
                onClick={(e) => e.stopPropagation()}>
                {truncHash(cycle.tx_hash)}
              </a>
              <Copy text={cycle.tx_hash} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
