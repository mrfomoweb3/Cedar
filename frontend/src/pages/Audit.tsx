import { useMemo, useState } from 'react';
import type { Cycle } from '../api';
import { api } from '../api';
import { Copy } from '../components/Copy';
import { fmtDateTime, fmtNum, outcomeLabel, outcomeVariant, plainReasoning, truncHash } from '../format';
import { usePoll } from '../hooks';

const FILTERS = ['ALL', 'EXECUTED', 'BLOCKED', 'HOLD', 'VALIDATION_FAILED'] as const;

export function Audit() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('ALL');
  const [q, setQ] = useState('');
  const { data } = usePoll(() => api.audit(200, 0, filter === 'ALL' ? undefined : filter), 3000);

  const rows = useMemo(() => {
    const cycles = data?.cycles ?? [];
    if (!q) return cycles;
    const needle = q.toLowerCase();
    return cycles.filter((c) =>
      (c.reasoning ?? '').toLowerCase().includes(needle) ||
      (c.hold_reason ?? '').toLowerCase().includes(needle) ||
      (c.tx_hash ?? '').toLowerCase().includes(needle));
  }, [data, q]);

  const exportCsv = () => {
    const header = ['timestamp', 'result', 'action', 'from', 'to', 'amount', 'reasoning', 'tx_hash'];
    const lines = rows.map((c) => [
      new Date((c.finished_at ?? 0) * 1000).toISOString(),
      c.outcome, c.action ?? '', c.from_pool ?? '', c.to_pool ?? '', c.amount ?? '',
      `"${(c.reasoning ?? '').replace(/"/g, "'")}"`, c.tx_hash ?? '',
    ].join(','));
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'cedar_audit_log.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="flex between">
        <div>
          <div className="page-title">Audit Log</div>
          <div className="page-sub">Every cycle, every decision, every transaction — permanently listed.</div>
        </div>
        <button className="btn" onClick={exportCsv}>⭳ Export CSV</button>
      </div>

      <div className="flex between" style={{ marginBottom: 16 }}>
        <div className="flex gap">
          {FILTERS.map((f) => (
            <button key={f} className={`btn ${filter === f ? 'btn-primary' : ''}`} onClick={() => setFilter(f)}>
              {f === 'ALL' ? 'All' : outcomeLabel(f as Cycle['outcome'])}
            </button>
          ))}
        </div>
        <input type="text" placeholder="search reasoning / tx…" value={q}
          onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 280 }} />
      </div>

      <div className="card">
        <table>
          <thead>
            <tr><th>Timestamp</th><th>Result</th><th>Reasoning</th><th>Checks</th><th>Tx Hash</th></tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={5}><div className="empty">no matching cycles</div></td></tr>}
            {rows.map((c) => (
              <tr key={c.id}>
                <td className="mono" style={{ whiteSpace: 'nowrap' }}>{fmtDateTime(c.finished_at)}</td>
                <td><span className={`tag ${outcomeVariant(c.outcome)}`}>{outcomeLabel(c.outcome)}</span></td>
                <td style={{ maxWidth: 420 }}>
                  <span style={{ fontSize: 13, lineHeight: 1.55 }}>
                    {c.action === 'REALLOCATE' && c.from_pool && (
                      <span className="mono" style={{ fontWeight: 600, color: 'var(--text)' }}>
                        {fmtNum(c.amount)} {c.from_pool} → {c.to_pool}.{' '}
                      </span>
                    )}
                    {plainReasoning(c.reasoning ?? c.hold_reason)}
                  </span>
                </td>
                <td className="mono">
                  {c.recheck_agrees ? <span className="s-live">✓</span> : <span className="s-error">✗</span>}
                  {' '}
                  {c.guardrails.length > 0 && (c.guardrails.every((g) => g.passed)
                    ? <span className="s-live">✓{c.guardrails.length}</span>
                    : <span className="s-blocked">⚑</span>)}
                </td>
                <td>
                  {c.tx_hash ? (
                    <span className="mono">
                      <a className="txhash" href={c.explorer_url} target="_blank" rel="noreferrer">{truncHash(c.tx_hash, 6)}</a>
                      <Copy text={c.tx_hash} />
                    </span>
                  ) : <span className="muted">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
