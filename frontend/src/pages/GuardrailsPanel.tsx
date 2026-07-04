import { api } from '../api';
import { fmtDateTime, fmtNum, outcomeLabel } from '../format';
import { usePoll } from '../hooks';

export function GuardrailsPanel() {
  const { data: gr } = usePoll(api.guardrails, 3000);
  const { data: feed } = usePoll(() => api.feed(100), 4000);

  const counts = gr?.trigger_counts ?? {};
  const cfg = gr?.config;

  const cycles = feed?.cycles ?? [];
  const total = cycles.length;
  const agree = cycles.filter((c) => c.recheck_agrees).length;
  const agreePct = total ? Math.round((agree / total) * 100) : 100;

  const lastTrigger = (name: string) => {
    const c = (gr?.blocked_history ?? []).find((x) =>
      x.guardrails.some((g) => g.name === name && !g.passed));
    return c ? fmtDateTime(c.finished_at) : '—';
  };

  const CARDS = [
    { key: 'position_cap', name: 'Position Size Cap', threshold: `${fmtNum(cfg?.max_reallocation_pct, 0)}% / cycle` },
    { key: 'cooldown', name: 'Cooldown / Rate Limit', threshold: `${fmtNum((cfg?.cooldown_seconds ?? 0) / 3600, 1)}h between moves` },
    { key: 'cost_check', name: 'Slippage &amp; Cost Check', threshold: 'gain must exceed gas + slippage' },
    { key: 'anomaly_recheck', name: 'Data Anomaly Circuit Breaker', threshold: `APY ∈ [${cfg?.apy_bounds?.[0]}, ${cfg?.apy_bounds?.[1]}]%` },
  ];

  return (
    <>
      <div className="page-title">Guardrails &amp; Safety</div>
      <div className="page-sub">The safety architecture, made inspectable. Every block below is real, logged, and named.</div>

      {gr?.cross_source && (
        <div className="card" style={{ marginBottom: 16,
          borderLeft: `3px solid ${gr.cross_source.verified ? 'var(--live)' : 'var(--blocked)'}` }}>
          <div className="flex between">
            <div style={{ fontWeight: 600 }}>Data Provenance — Cross-Source Verification</div>
            <span className={gr.cross_source.verified ? 'badge-ok' : 'badge-warn'}>
              {gr.cross_source.verified
                ? `✓ verified · ${gr.cross_source.verified_pools}/${gr.cross_source.total_pools} pools`
                : `⚑ single-source · unverified`}
            </span>
          </div>
          <div className="mono" style={{ marginTop: 8, fontSize: 12,
            color: gr.cross_source.verified ? 'var(--live)' : 'var(--blocked)' }}>
            {gr.cross_source.note}
          </div>
          <div className="muted" style={{ marginTop: 8, fontSize: 12, lineHeight: 1.6 }}>
            {gr.cross_source.detail}
          </div>
        </div>
      )}

      <div className="grid-2" style={{ marginBottom: 16 }}>
        {CARDS.map((c) => {
          const n = counts[c.key] ?? 0;
          return (
            <div className="card" key={c.key}>
              <div className="flex between">
                <div style={{ fontWeight: 600 }} dangerouslySetInnerHTML={{ __html: c.name }} />
                <span className={n > 0 ? 'badge-warn' : 'badge-ok'}>
                  {n > 0 ? `triggered ${n}×` : 'never triggered'}
                </span>
              </div>
              <div className="muted mono" style={{ marginTop: 10, fontSize: 12 }}>threshold: {c.threshold}</div>
              <div className="muted mono" style={{ marginTop: 4, fontSize: 12 }}>last trigger: {lastTrigger(c.key)}</div>
            </div>
          );
        })}

        <div className="card">
          <div className="flex between">
            <div style={{ fontWeight: 600 }}>Deterministic Recheck</div>
            <span className={agreePct === 100 ? 'badge-ok' : 'badge-warn'}>{agreePct}% agreement</span>
          </div>
          <div className="muted mono" style={{ marginTop: 10, fontSize: 12 }}>
            agent decision vs. code-computed decision
          </div>
          <div className="metric-lg" style={{ marginTop: 8 }}>
            {agree}<span className="metric-sm"> / {total} cycles agree</span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Trigger History</div>
        {(gr?.blocked_history?.length ?? 0) === 0 ? (
          <div className="empty">no guardrail has fired yet</div>
        ) : (
          <table>
            <thead><tr><th>Time</th><th>Guardrail</th><th>Blocked Action</th><th>Reason</th></tr></thead>
            <tbody>
              {gr!.blocked_history.map((c) => {
                const failed = c.guardrails.find((g) => !g.passed);
                return (
                  <tr key={c.id}>
                    <td className="mono">{fmtDateTime(c.finished_at)}</td>
                    <td><span className="tag blocked">{failed?.name ?? 'recheck'}</span></td>
                    <td className="mono">{c.action === 'REALLOCATE'
                      ? `${fmtNum(c.amount)} ${c.from_pool}→${c.to_pool}` : outcomeLabel(c.outcome)}</td>
                    <td>{c.hold_reason}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
