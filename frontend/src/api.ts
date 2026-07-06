// Cedar API client — talks to the FastAPI control plane (api/main.py).
// VITE_API_BASE unset (dev) -> localhost:8000; set to "" -> same-origin
// (when the backend serves the built dashboard); set to a URL -> that host.
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export interface Policy {
  min_apy_delta: number;
  max_reallocation_pct: number;
  cooldown_seconds: number;
  allowed_pools: string[];
  apy_min_bound: number;
  apy_max_bound: number;
  freshness_seconds: number;
  cross_source_tolerance: number;
  expected_slippage_pct: number;
  hold_period_days: number;
}

export interface Status {
  status: string;
  paused: boolean;
  next_cycle_at: number | null;
  next_cycle_in: number | null;
  interval_seconds: number;
  total_cycles: number;
}

export interface PoolReading { pool_id: string; apy: number; allocation: number; source: string; }
export interface Snapshot {
  pools: Record<string, PoolReading>;
  gas_estimate: number;
  cross_source_apy: Record<string, number>;
  implied_price?: Record<string, number>;
  cross_source_price?: Record<string, number>;
  cross_source_verified?: Record<string, boolean>;
  timestamp: number;
  total_value?: number;
}

export interface CrossSourceStatus {
  verified: boolean;
  verified_pools: number;
  total_pools: number;
  single_source: boolean;
  note: string;
  detail: string;
}
export interface GuardrailResult { name: string; passed: boolean; detail: string; }

export interface Cycle {
  id: string;
  started_at: number;
  finished_at: number | null;
  outcome: 'HOLD' | 'BLOCKED' | 'EXECUTED' | 'EXECUTION_FAILED' | 'VALIDATION_FAILED';
  action: string | null;
  from_pool: string | null;
  to_pool: string | null;
  amount: number | null;
  confidence: number | null;
  reasoning: string | null;
  recheck_agrees: boolean;
  hold_reason: string | null;
  tx_hash: string | null;
  snapshot: Snapshot | null;
  guardrails: GuardrailResult[];
  explorer_url?: string;
}

export interface Portfolio {
  allocations: Record<string, number>;
  total_value: number;
  weights: Record<string, number>;
}

export interface Guardrails {
  config: {
    cooldown_seconds: number;
    max_reallocation_pct: number;
    min_apy_delta: number;
    apy_bounds: [number, number];
    cross_source_tolerance: number;
  };
  trigger_counts: Record<string, number>;
  blocked_history: Cycle[];
  cross_source?: CrossSourceStatus;
}

// Optional admin token for locked deployments (CEDAR_ADMIN_TOKEN set on the
// server). The owner stores it once in the browser; it's sent on write calls
// and never baked into the bundle. Public visitors without it get read-only.
function adminHeaders(): Record<string, string> {
  try {
    const t = localStorage.getItem('cedar-admin-token');
    return t ? { 'X-Admin-Token': t } : {};
  } catch {
    return {};
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...adminHeaders() },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  base: BASE,
  status: () => req<Status>('/agent/status'),
  feed: (limit = 50) => req<{ cycles: Cycle[] }>(`/agent/feed?limit=${limit}`),
  portfolio: () => req<Portfolio>('/agent/portfolio'),
  guardrails: () => req<Guardrails>('/agent/guardrails'),
  audit: (limit = 50, offset = 0, outcome?: string) =>
    req<{ total: number; limit: number; offset: number; cycles: Cycle[] }>(
      `/agent/audit?limit=${limit}&offset=${offset}${outcome ? `&outcome=${outcome}` : ''}`),
  getPolicy: () => req<Policy>('/agent/policy'),
  setPolicy: (p: Policy) => req<{ ok: boolean }>('/agent/policy', { method: 'POST', body: JSON.stringify(p) }),
  pause: () => req<{ ok: boolean; paused: boolean }>('/agent/pause', { method: 'POST' }),
  resume: () => req<{ ok: boolean; paused: boolean }>('/agent/resume', { method: 'POST' }),
  onboard: (policy: Policy, wallet_address?: string) =>
    req<{ ok: boolean }>('/agent/onboard', { method: 'POST', body: JSON.stringify({ policy, wallet_address }) }),
  runOnce: () => req<{ ok: boolean; outcome: string; tx_hash: string | null }>('/agent/run-once', { method: 'POST' }),
  demo: (name: 'spike' | 'bad-data' | 'divergence') =>
    req<{ ok: boolean; seeded: string }>(`/agent/demo/${name}`, { method: 'POST' }),
};
