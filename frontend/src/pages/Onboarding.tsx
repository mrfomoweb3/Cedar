import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Policy } from '../api';
import { api } from '../api';
import { PolicyForm } from '../components/PolicyForm';
import { fmtNum } from '../format';

export function Onboarding() {
  const [step, setStep] = useState(1);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [wallet, setWallet] = useState<string | null>(null);
  const nav = useNavigate();

  useEffect(() => { api.getPolicy().then(setPolicy); }, []);

  const connect = () => setWallet('01a2f3c4b5d6e7f8090a1b2c3d4e5f60718293a4b5c6d7e8f90112233445566');

  const activate = async () => {
    if (!policy) return;
    await api.onboard(policy, wallet ?? undefined);
    nav('/app');
  };

  if (!policy) return <div className="empty">loading…</div>;

  return (
    <div className="wizard">
      <div className="steps">
        {[1, 2, 3].map((s) => <div key={s} className={`step-pill ${s <= step ? 'done' : ''}`} />)}
      </div>

      {step === 1 && (
        <div className="card">
          <div className="card-title">Step 1 — Agent Wallet</div>
          <div className="flex between" style={{ marginBottom: 16 }}>
            <span style={{ fontWeight: 600, fontSize: 16 }}>Connect Agent Wallet</span>
            <span className="chip testnet">CASPER TESTNET</span>
          </div>
          {wallet ? (
            <>
              <div className="metric-sm muted">Connected address</div>
              <div className="mono" style={{ wordBreak: 'break-all', margin: '4px 0 14px' }}>{wallet}</div>
              <div className="metric-sm muted">Balance</div>
              <div className="metric-lg">1,000.00 <span className="metric-sm">CSPR</span></div>
            </>
          ) : (
            <button className="btn btn-primary btn-lg" onClick={connect}>Connect via CSPR.click</button>
          )}
          <div className="flex between" style={{ marginTop: 24 }}>
            <span />
            <button className="btn btn-primary" disabled={!wallet} onClick={() => setStep(2)}>Next →</button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="card">
          <div className="card-title">Step 2 — Define Policy</div>
          <PolicyForm policy={policy} onChange={setPolicy} />
          <div className="flex between" style={{ marginTop: 8 }}>
            <button className="btn" onClick={() => setStep(1)}>← Back</button>
            <button className="btn btn-primary" onClick={() => setStep(3)}>Review →</button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="card">
          <div className="card-title">Step 3 — Review &amp; Activate</div>
          <p style={{ lineHeight: 1.7, marginBottom: 20 }}>
            Agent will reallocate up to <b className="mono">{fmtNum(policy.max_reallocation_pct, 0)}%</b> of portfolio
            when APY delta exceeds <b className="mono">{fmtNum(policy.min_apy_delta, 1)}%</b>, no more than once every{' '}
            <b className="mono">{fmtNum(policy.cooldown_seconds / 3600, 1)}h</b>, only between:{' '}
            <b>{policy.allowed_pools.join(', ')}</b>.
          </p>
          <button className="btn btn-primary btn-lg" style={{ width: '100%' }} onClick={activate}>
            Activate Agent
          </button>
          <p className="muted" style={{ fontSize: 12, marginTop: 12, lineHeight: 1.6 }}>
            The agent will observe, reason, and execute independently based on this policy.
            You can pause it at any time from the Dashboard.
          </p>
          <div className="flex" style={{ marginTop: 16 }}>
            <button className="btn" onClick={() => setStep(2)}>← Back</button>
          </div>
        </div>
      )}
    </div>
  );
}
