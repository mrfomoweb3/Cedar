import type { Cycle } from './api';

// Restrained categorical palette on white: green accent + warm amber + slate.
export const POOL_COLORS: Record<string, string> = {
  PoolA: '#1A5C2E',
  PoolB: '#C77D3A',
  PoolC: '#3E6D8E',
};

export function fmtNum(n: number | null | undefined, dp = 2): string {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

export function fmtTime(ts: number | null | undefined): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function fmtDateTime(ts: number | null | undefined): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString([], {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export function truncHash(h: string | null, n = 8): string {
  if (!h) return '—';
  return h.length > n * 2 ? `${h.slice(0, n)}…${h.slice(-n)}` : h;
}

export function fmtCountdown(secs: number | null | undefined): string {
  if (secs === null || secs === undefined) return '—';
  const s = Math.max(0, Math.floor(secs));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

/** Map an outcome to the css variant used across cards/tags/borders. */
export function outcomeVariant(o: Cycle['outcome']): 'executed' | 'blocked' | 'hold' | 'failed' {
  switch (o) {
    case 'EXECUTED': return 'executed';
    case 'BLOCKED': return 'blocked';
    case 'VALIDATION_FAILED':
    case 'EXECUTION_FAILED': return 'failed';
    default: return 'hold';
  }
}

export function outcomeLabel(o: Cycle['outcome']): string {
  return { EXECUTED: 'Reallocated', BLOCKED: 'Blocked', HOLD: 'Hold',
    VALIDATION_FAILED: 'Halted', EXECUTION_FAILED: 'Exec Failed' }[o] || o;
}

/** Map live agent status string to a chip variant. */
export function statusVariant(s: string): 'live' | 'hold' | 'blocked' | 'error' {
  const v = s.toLowerCase();
  if (['observing', 'reasoning', 'validating', 'executing'].includes(v)) return 'live';
  if (['blocked'].includes(v)) return 'blocked';
  if (['error', 'halted'].includes(v)) return 'error';
  return 'hold';
}
