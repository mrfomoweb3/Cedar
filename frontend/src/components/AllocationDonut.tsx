import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { POOL_COLORS, fmtNum } from '../format';

export function AllocationDonut({ allocations }: { allocations: Record<string, number> }) {
  const data = Object.entries(allocations)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  if (data.length === 0) return <div className="empty">no allocation</div>;

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72}
          paddingAngle={2} stroke="none" isAnimationActive={false}>
          {data.map((d) => <Cell key={d.name} fill={POOL_COLORS[d.name] || '#888'} />)}
        </Pie>
        <Tooltip
          contentStyle={{ background: 'var(--elevated)', border: '1px solid var(--border)',
            borderRadius: 10, color: 'var(--text)', fontSize: 12.5 }}
          formatter={(v) => [`${fmtNum(Number(v))} CSPR`, '']} />
      </PieChart>
    </ResponsiveContainer>
  );
}
