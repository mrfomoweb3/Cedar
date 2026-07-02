import { api } from '../api';
import { AllocationDonut } from '../components/AllocationDonut';
import { ReasoningCard } from '../components/ReasoningCard';
import { POOL_COLORS, fmtNum } from '../format';
import { usePoll } from '../hooks';

export function Dashboard() {
  const { data: feed } = usePoll(() => api.feed(30), 2500);
  const { data: portfolio } = usePoll(api.portfolio, 3000);
  const { data: guardrails } = usePoll(api.guardrails, 4000);
  const { data: policy } = usePoll(api.getPolicy, 8000);

  const cycles = feed?.cycles ?? [];

  // Live guardrail status from the most recent cycle.
  const latest = cycles[0];
  const grStatus = (name: string) => {
    const g = latest?.guardrails.find((x) => x.name === name);
    if (!g) return { ok: true, label: 'ready' };
    return { ok: g.passed, label: g.passed ? 'ok' : 'flagged' };
  };
  const dataValid = latest ? latest.outcome !== 'VALIDATION_FAILED' : true;

  const seed = async (name: 'spike' | 'bad-data' | 'divergence') => {
    await api.demo(name);
    await api.runOnce();
  };

  return (
    <div className="dash-grid">
      {/* Zone B — live reasoning feed */}
      <div className="stack">
        <div className="flex between">
          <div>
            <div className="page-title">Live Reasoning Feed</div>
            <div className="page-sub" style={{ marginBottom: 0 }}>
              The agent's observe → reason → act loop, newest first.
            </div>
          </div>
          <div className="flex gap">
            <button className="btn" onClick={() => seed('spike')} title="Seed an APY spike">▲ Spike APY</button>
            <button className="btn" onClick={() => seed('bad-data')} title="Seed bad data">⚠ Bad Data</button>
            <button className="btn btn-primary" onClick={() => api.runOnce()}>▶ Run Cycle</button>
          </div>
        </div>
        <div className="feed">
          {cycles.length === 0 && <div className="empty">waiting for first cycle…</div>}
          {cycles.map((c, i) => <ReasoningCard key={c.id} cycle={c} defaultOpen={i === 0} />)}
        </div>
      </div>

      {/* Zone C — right sidebar */}
      <div className="stack">
        <div className="card">
          <div className="card-title">Current Allocation</div>
          <AllocationDonut allocations={portfolio?.allocations ?? {}} />
          <div className="stack" style={{ gap: 6, marginTop: 12 }}>
            {Object.entries(portfolio?.allocations ?? {}).map(([pool, amt]) => (
              <div className="flex between" key={pool}>
                <span className="flex gap" style={{ gap: 8 }}>
                  <span className="dot" style={{ background: POOL_COLORS[pool] }} />
                  {pool}
                </span>
                <span className="mono">{fmtNum(amt)} CSPR
                  <span className="muted"> · {fmtNum((portfolio?.weights[pool] ?? 0) * 100, 1)}%</span>
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Guardrail Status</div>
          {[
            { key: 'cooldown', label: 'Cooldown', ok: grStatus('cooldown').ok },
            { key: 'position_cap', label: 'Position Cap', ok: grStatus('position_cap').ok },
            { key: 'data', label: 'Data Validity', ok: dataValid },
          ].map((g) => (
            <div className="indicator-row" key={g.key}>
              <span>{g.label}</span>
              <span className={g.ok ? 'badge-ok' : 'badge-warn'}>
                {g.ok ? '✓ ok' : '⚑ flagged'}
              </span>
            </div>
          ))}
          <div className="indicator-row">
            <span>Recheck Agreement</span>
            <span className="badge-ok">
              {latest ? (latest.recheck_agrees ? '✓ agrees' : '✗ disagree') : '—'}
            </span>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Policy Snapshot</div>
          <div className="stack" style={{ gap: 8 }}>
            <div className="flex between"><span className="muted">Min APY delta</span><span className="mono">{fmtNum(policy?.min_apy_delta, 1)}%</span></div>
            <div className="flex between"><span className="muted">Max per cycle</span><span className="mono">{fmtNum(policy?.max_reallocation_pct, 0)}%</span></div>
            <div className="flex between"><span className="muted">Cooldown</span><span className="mono">{fmtNum((policy?.cooldown_seconds ?? 0) / 3600, 1)}h</span></div>
            <div className="flex between"><span className="muted">Blocks triggered</span>
              <span className="mono">{Object.values(guardrails?.trigger_counts ?? {}).reduce((a, b) => a + b, 0)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
