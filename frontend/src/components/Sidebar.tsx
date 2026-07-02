import { NavLink } from 'react-router-dom';

const NAV = [
  { to: '/', label: 'Live Dashboard', ico: '◉', end: true },
  { to: '/portfolio', label: 'Portfolio', ico: '▤' },
  { to: '/guardrails', label: 'Guardrails', ico: '⛨' },
  { to: '/audit', label: 'Audit Log', ico: '☰' },
  { to: '/settings', label: 'Policy Settings', ico: '⚙' },
  { to: '/onboarding', label: 'Agent Setup', ico: '✦' },
];

export function Sidebar() {
  return (
    <div className="sidebar">
      <div className="brand">
        <span className="brand-mark">C</span>
        Cedar
      </div>
      <nav className="stack" style={{ gap: 4 }}>
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-ico">{n.ico}</span>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div style={{ marginTop: 'auto', padding: '12px', color: 'var(--text-tertiary)', fontSize: 11 }}>
        <span className="chip testnet">CASPER TESTNET</span>
        <div className="mono" style={{ marginTop: 10 }}>Autonomous yield router</div>
      </div>
    </div>
  );
}
