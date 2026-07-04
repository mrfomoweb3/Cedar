import { useMemo } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import { AllocationDonut } from '../components/AllocationDonut';
import { ReasoningCard } from '../components/ReasoningCard';
import { POOL_COLORS, fmtNum, fmtTime } from '../format';
import { usePoll } from '../hooks';

export function Dashboard() {
  const { data: feed } = usePoll(() => api.feed(40), 2500);
  const { data: portfolio } = usePoll(api.portfolio, 3000);
  const { data: guardrails } = usePoll(api.guardrails, 4000);
  const { data: policy } = usePoll(api.getPolicy, 8000);
  const { data: status } = usePoll(api.status, 2000);

  const cycles = feed?.cycles ?? [];
  const latest = cycles[0];
  const pools = Object.keys(portfolio?.allocations ?? {});
  const activePools = pools.filter((p) => (portfolio?.allocations[p] ?? 0) > 0).length;

  const executed = cycles.filter((c) => c.outcome === 'EXECUTED').length;
  const blocks = Object.values(guardrails?.trigger_counts ?? {}).reduce((a, b) => a + b, 0);
  const agree = cycles.filter((c) => c.recheck_agrees).length;
  const agreePct = cycles.length ? Math.round((agree / cycles.length) * 100) : 100;

  const singleSource = guardrails?.cross_source?.single_source ?? false;
  const dataValid = latest ? latest.outcome !== 'VALIDATION_FAILED' : true;
  const grStatus = (name: string) => {
    const g = latest?.guardrails.find((x) => x.name === name);
    return g ? g.passed : true;
  };

  const series = useMemo(() => {
    const rows = [...cycles].reverse().filter((c) => c.snapshot);
    return rows.map((c) => {
      const row: Record<string, number | string> = { t: fmtTime(c.finished_at ?? c.started_at) };
      for (const [pid, r] of Object.entries(c.snapshot!.pools)) row[pid] = r.allocation;
      return row;
    });
  }, [cycles]);

  const seed = async (name: 'spike' | 'bad-data') => { await api.demo(name); await api.runOnce(); };

  const TILES = [
    { ico: '◎', label: 'Portfolio value', value: `${fmtNum(portfolio?.total_value)}`, unit: 'CSPR',
      chip: `${activePools}/${pools.length} pools`, tone: 'flat' as const },
    { ico: '↻', label: 'Autonomous cycles', value: `${status?.total_cycles ?? cycles.length}`, unit: '',
      chip: '● live', tone: 'up' as const },
    { ico: '⛨', label: 'Recheck agreement', value: `${agreePct}`, unit: '%',
      chip: `${agree}/${cycles.length}`, tone: agreePct === 100 ? 'up' as const : 'flat' as const },
    { ico: '⦸', label: 'Unsafe moves blocked', value: `${blocks}`, unit: '',
      chip: 'guardrails', tone: blocks > 0 ? 'down' as const : 'flat' as const },
  ];

  return (
    <>
      <div className="flex between" style={{ marginBottom: 4 }}>
        <div>
          <div className="page-title">Live Dashboard</div>
          <div className="page-sub" style={{ marginBottom: 0 }}>
            The agent is observing, reasoning, and acting on its own — here's what it's doing right now.
          </div>
        </div>
      </div>

      {/* stat tiles */}
      <div className="statgrid" style={{ marginTop: 20 }}>
        {TILES.map((t) => (
          <div className="stat" key={t.label}>
            <div className="stat-top">
              <span className="stat-ico">{t.ico}</span>
              <span className={`stat-delta ${t.tone}`}>{t.chip}</span>
            </div>
            <div className="stat-value">{t.value}{t.unit && <span className="metric-sm" style={{ marginLeft: 5 }}>{t.unit}</span>}</div>
            <div className="stat-label">{t.label}</div>
          </div>
        ))}
      </div>

      <div className="dash-grid">
        {/* left column */}
        <div className="stack">
          <div className="card">
            <div className="flex between" style={{ marginBottom: 6 }}>
              <div className="card-title" style={{ marginBottom: 0 }}>Allocation over time</div>
              <div className="flex gap">
                <button className="btn" onClick={() => seed('spike')} title="Seed an APY spike (mock mode)">▲ Spike</button>
                <button className="btn" onClick={() => seed('bad-data')} title="Seed bad data (mock mode)">⚠ Bad data</button>
                <button className="btn btn-primary" onClick={() => api.runOnce()}>▶ Run cycle</button>
              </div>
            </div>
            {series.length < 2 ? <div className="empty">gathering cycles…</div> : (
              <ResponsiveContainer width="100%" height={230}>
                <AreaChart data={series} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid stroke="#EEE" strokeDasharray="0" vertical={false} />
                  <XAxis dataKey="t" stroke="#9AA0A6" fontSize={11} tickLine={false} axisLine={false} minTickGap={40} />
                  <YAxis stroke="#9AA0A6" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: '#fff', border: '1px solid #E7E7E7', borderRadius: 10,
                    boxShadow: '0 2px 8px rgba(16,24,40,.08)', fontSize: 12.5 }} />
                  {pools.map((p) => (
                    <Area key={p} type="monotone" dataKey={p} stackId="1" isAnimationActive={false}
                      stroke={POOL_COLORS[p]} fill={POOL_COLORS[p]} fillOpacity={0.14} strokeWidth={2} />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="card">
            <div className="flex between" style={{ marginBottom: 14 }}>
              <div className="card-title" style={{ marginBottom: 0 }}>Live reasoning feed</div>
              <span className="metric-sm muted">newest first · updates every cycle</span>
            </div>
            <div className="feed">
              {cycles.length === 0 && <div className="empty">waiting for first cycle…</div>}
              {cycles.slice(0, 8).map((c, i) => <ReasoningCard key={c.id} cycle={c} defaultOpen={i === 0} />)}
            </div>
          </div>
        </div>

        {/* right column */}
        <div className="stack">
          <div className="card">
            <div className="card-title">Current allocation</div>
            <AllocationDonut allocations={portfolio?.allocations ?? {}} />
            <div className="stack" style={{ gap: 8, marginTop: 14 }}>
              {Object.entries(portfolio?.allocations ?? {}).map(([pool, amt]) => (
                <div className="flex between" key={pool} style={{ fontSize: 13.5 }}>
                  <span className="flex gap" style={{ gap: 8 }}>
                    <span className="dot" style={{ background: POOL_COLORS[pool], width: 9, height: 9 }} />
                    {pool}
                  </span>
                  <span className="mono">{fmtNum(amt)} <span className="muted">· {fmtNum((portfolio?.weights[pool] ?? 0) * 100, 1)}%</span></span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-title">Guardrail status</div>
            {[
              { label: 'Cooldown', ok: grStatus('cooldown') },
              { label: 'Position cap', ok: grStatus('position_cap') },
              { label: 'Data validity', ok: dataValid },
            ].map((g) => (
              <div className="indicator-row" key={g.label}>
                <span style={{ fontSize: 13.5 }}>{g.label}</span>
                <span className={g.ok ? 'badge-ok' : 'badge-warn'}>{g.ok ? '✓ ok' : '⚑ flagged'}</span>
              </div>
            ))}
            <div className="indicator-row">
              <span style={{ fontSize: 13.5 }}>Recheck agreement</span>
              <span className="badge-ok">{latest ? (latest.recheck_agrees ? '✓ agrees' : '✗ disagree') : '—'}</span>
            </div>
            <div className="indicator-row">
              <span style={{ fontSize: 13.5 }}>Cross-source</span>
              <span className={singleSource ? 'badge-warn' : 'badge-ok'}>
                {latest ? (singleSource ? '⚑ single-source' : '✓ verified') : '—'}
              </span>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Policy snapshot</div>
            <div className="stack" style={{ gap: 10, fontSize: 13.5 }}>
              <div className="flex between"><span className="muted">Min APY delta</span><span className="mono">{fmtNum(policy?.min_apy_delta, 1)}%</span></div>
              <div className="flex between"><span className="muted">Max per cycle</span><span className="mono">{fmtNum(policy?.max_reallocation_pct, 0)}%</span></div>
              <div className="flex between"><span className="muted">Cooldown</span><span className="mono">{fmtNum((policy?.cooldown_seconds ?? 0) / 3600, 1)}h</span></div>
              <div className="flex between"><span className="muted">On-chain moves</span><span className="mono">{executed}</span></div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
