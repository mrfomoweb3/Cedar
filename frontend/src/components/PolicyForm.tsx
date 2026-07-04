import type { Policy } from '../api';
import { fmtNum } from '../format';

const ALL_POOLS = ['PoolA', 'PoolB', 'PoolC'];

interface Props {
  policy: Policy;
  onChange: (p: Policy) => void;
}

/** The shared policy controls used by Onboarding Step 2 and Settings.
    Every control is annotated as a guardrail, not just a setting. */
export function PolicyForm({ policy, onChange }: Props) {
  const set = (patch: Partial<Policy>) => onChange({ ...policy, ...patch });

  return (
    <div>
      <div className="field">
        <label>
          Min APY delta to trigger reallocation
          <span className="mono" style={{ float: 'right', color: 'var(--accent)' }}>
            {fmtNum(policy.min_apy_delta, 1)}%
          </span>
        </label>
        <input type="range" min={0.5} max={10} step={0.5} value={policy.min_apy_delta}
          onChange={(e) => set({ min_apy_delta: +e.target.value })} />
        <div className="hint">Guardrail: the agent won't chase noise — it only moves when the yield gap clears this bar.</div>
      </div>

      <div className="field">
        <label>
          Max % of portfolio movable per cycle
          <span className="mono" style={{ float: 'right', color: 'var(--accent)' }}>
            {fmtNum(policy.max_reallocation_pct, 0)}%
          </span>
        </label>
        <input type="range" min={5} max={50} step={5} value={policy.max_reallocation_pct}
          onChange={(e) => set({ max_reallocation_pct: +e.target.value })} />
        <div className="hint">Guardrail: caps blast radius. Hard ceiling 50% — the agent can never move everything at once.</div>
      </div>

      <div className="field">
        <label>Cooldown between reallocations (hours)</label>
        <input type="number" min={0} step={0.5} value={policy.cooldown_seconds / 3600}
          onChange={(e) => set({ cooldown_seconds: +e.target.value * 3600 })} />
        <div className="hint">Guardrail: rate-limits action so a volatile market can't trigger churn.</div>
      </div>

      <div className="field">
        <label>Allowed pools</label>
        {ALL_POOLS.map((p) => (
          <label className="checkrow" key={p}>
            <input type="checkbox" checked={policy.allowed_pools.includes(p)}
              onChange={(e) => set({
                allowed_pools: e.target.checked
                  ? [...policy.allowed_pools, p]
                  : policy.allowed_pools.filter((x) => x !== p),
              })} />
            {p}
          </label>
        ))}
        <div className="hint">Guardrail: pre-vetted testnet pools only — no arbitrary pool injection.</div>
      </div>
    </div>
  );
}
