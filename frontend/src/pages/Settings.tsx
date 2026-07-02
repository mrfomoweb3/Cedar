import { useEffect, useState } from 'react';
import type { Policy } from '../api';
import { api } from '../api';
import { PolicyForm } from '../components/PolicyForm';

export function Settings() {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.getPolicy().then(setPolicy); }, []);

  const save = async () => {
    if (!policy) return;
    await api.setPolicy(policy);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!policy) return <div className="empty">loading policy…</div>;

  return (
    <div style={{ maxWidth: 620 }}>
      <div className="page-title">Agent Policy Settings</div>
      <div className="page-sub">Live control panel. No silent auto-apply — every change is explicit.</div>

      <div className="banner">Changes apply to the next reasoning cycle — this is a live autonomous system, not micromanaged in real time.</div>

      <div className="card">
        <PolicyForm policy={policy} onChange={setPolicy} />
        <div className="flex gap" style={{ marginTop: 8 }}>
          <button className="btn btn-primary" onClick={save}>Save Policy</button>
          {saved && <span className="badge-ok">✓ saved — applies next cycle</span>}
        </div>
      </div>
    </div>
  );
}
