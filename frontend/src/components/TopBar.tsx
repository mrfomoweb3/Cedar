import { api } from '../api';
import { fmtCountdown } from '../format';
import { usePoll } from '../hooks';
import { StatusChip } from './StatusChip';
import { ThemeToggle } from './ThemeToggle';

export function TopBar() {
  const { data: status, error, refresh } = usePoll(api.status, 1000);

  const paused = status?.paused ?? false;
  const offline = !!error && !status;

  const toggle = async () => {
    if (paused) await api.resume();
    else await api.pause();
    refresh();
  };

  return (
    <div className="topbar">
      <div className="flex gap" style={{ gap: 20 }}>
        <StatusChip status={offline ? 'offline' : (status?.status ?? 'idle')} />
        {offline && <span className="metric-sm" style={{ color: 'var(--error)' }}>API unreachable</span>}
        <span className="metric-sm">
          Next check in{' '}
          <span className="mono" style={{ color: 'var(--text)' }}>
            {fmtCountdown(status?.next_cycle_in)}
          </span>
        </span>
        <span className="metric-sm muted">{status?.total_cycles ?? 0} cycles</span>
      </div>
      <div className="topbar-right">
        <ThemeToggle />
        <button className={`btn ${paused ? 'btn-primary' : 'btn-danger'}`} onClick={toggle}>
          {paused ? '▶ Resume Agent' : '⏸ Pause Agent'}
        </button>
      </div>
    </div>
  );
}
