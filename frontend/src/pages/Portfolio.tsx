import { useMemo } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import { POOL_COLORS, fmtNum, fmtTime } from '../format';
import { usePoll } from '../hooks';

export function Portfolio() {
  const { data: portfolio } = usePoll(api.portfolio, 3000);
  const { data: feed } = usePoll(() => api.feed(100), 4000);
  const { data: guardrails } = usePoll(api.guardrails, 8000);

  const pools = Object.keys(portfolio?.allocations ?? {});

  // Reconstruct allocation-over-time from cycle snapshots (chronological).
  const series = useMemo(() => {
    const cycles = [...(feed?.cycles ?? [])].reverse();
    return cycles
      .filter((c) => c.snapshot)
      .map((c) => {
        const row: Record<string, number | string> = { t: fmtTime(c.finished_at ?? c.started_at) };
        for (const [pid, r] of Object.entries(c.snapshot!.pools)) row[pid] = r.allocation;
        return row;
      });
  }, [feed]);

  const lastRebalanced = (pool: string) => {
    const c = feed?.cycles.find((x) => x.outcome === 'EXECUTED' && (x.to_pool === pool || x.from_pool === pool));
    return c ? fmtTime(c.finished_at) : 'never';
  };
  const apy = (pool: string) => {
    const c = feed?.cycles.find((x) => x.snapshot?.pools[pool]);
    return c?.snapshot?.pools[pool].apy ?? null;
  };

  return (
    <>
      <div className="page-title">Portfolio &amp; Positions</div>
      <div className="page-sub">Current allocation and how the agent has moved capital over the run.</div>

      <div className="grid-3" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">Total Value</div>
          <div className="metric-lg">{fmtNum(portfolio?.total_value)} <span className="metric-sm">CSPR</span></div>
        </div>
        <div className="card">
          <div className="card-title">Active Pools</div>
          <div className="metric-lg">{pools.filter((p) => (portfolio?.allocations[p] ?? 0) > 0).length}<span className="metric-sm"> / {pools.length}</span></div>
        </div>
        <div className="card">
          <div className="card-title">Reallocations</div>
          <div className="metric-lg">{feed?.cycles.filter((c) => c.outcome === 'EXECUTED').length ?? 0}</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">Allocation Over Time</div>
        {series.length < 2 ? <div className="empty">not enough cycles yet</div> : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={series}>
              <CartesianGrid stroke="#2A2E35" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="t" stroke="#5C6470" fontSize={11} tickLine={false} />
              <YAxis stroke="#5C6470" fontSize={11} tickLine={false} />
              <Tooltip contentStyle={{ background: '#1C1F24', border: '1px solid #2A2E35', borderRadius: 6, fontFamily: 'JetBrains Mono' }} />
              {pools.map((p) => (
                <Area key={p} type="monotone" dataKey={p} stackId="1" isAnimationActive={false}
                  stroke={POOL_COLORS[p]} fill={POOL_COLORS[p]} fillOpacity={0.25} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <div className="card-title">Positions</div>
        <table>
          <thead>
            <tr><th>Pool</th><th className="num">Allocation %</th><th className="num">Amount</th><th className="num">APY</th><th>Last Rebalanced</th></tr>
          </thead>
          <tbody>
            {pools.map((p) => (
              <tr key={p}>
                <td><span className="dot" style={{ background: POOL_COLORS[p], display: 'inline-block', marginRight: 8 }} />{p}</td>
                <td className="num">{fmtNum((portfolio?.weights[p] ?? 0) * 100, 1)}%</td>
                <td className="num">{fmtNum(portfolio?.allocations[p])}</td>
                <td className="num">{apy(p) !== null ? `${fmtNum(apy(p))}%` : '—'}</td>
                <td>{lastRebalanced(p)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="muted mono" style={{ marginTop: 12, fontSize: 12 }}>
        {Object.values(guardrails?.trigger_counts ?? {}).reduce((a, b) => a + b, 0)} guardrail blocks recorded this run.
      </div>
    </>
  );
}
