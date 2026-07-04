import { NavLink } from 'react-router-dom';
import mark from '../assets/cedar-mark.png';

const NAV = [
  { to: '/app', label: 'Live Dashboard', ico: '◉', end: true },
  { to: '/app/portfolio', label: 'Portfolio', ico: '▤' },
  { to: '/app/guardrails', label: 'Guardrails', ico: '⛨' },
  { to: '/app/audit', label: 'Audit Log', ico: '☰' },
  { to: '/app/settings', label: 'Policy Settings', ico: '⚙' },
  { to: '/app/onboarding', label: 'Agent Setup', ico: '✦' },
];

export function Sidebar() {
  return (
    <div className="sidebar">
      <NavLink to="/" className="brand" style={{ textDecoration: 'none' }}>
        <img src={mark} className="brand-mark-img" alt="" aria-hidden="true" />
        Cedar
      </NavLink>
      <nav className="stack" style={{ gap: 4 }}>
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-ico">{n.ico}</span>
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div style={{ marginTop: 'auto', padding: '12px', color: 'var(--text-3)', fontSize: 11 }}>
        <span className="chip testnet">CASPER TESTNET</span>
        <div className="mono" style={{ marginTop: 10 }}>Autonomous yield router</div>
      </div>
    </div>
  );
}
