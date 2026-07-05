import { Outlet, Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { Audit } from './pages/Audit';
import { Dashboard } from './pages/Dashboard';
import { Docs } from './pages/Docs';
import { GuardrailsPanel } from './pages/GuardrailsPanel';
import { Landing } from './pages/Landing';
import { Onboarding } from './pages/Onboarding';
import { Portfolio } from './pages/Portfolio';
import { Settings } from './pages/Settings';

function Shell() {
  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <TopBar />
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/docs" element={<Docs />} />
      <Route path="/app" element={<Shell />}>
        <Route index element={<Dashboard />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="guardrails" element={<GuardrailsPanel />} />
        <Route path="audit" element={<Audit />} />
        <Route path="settings" element={<Settings />} />
        <Route path="onboarding" element={<Onboarding />} />
      </Route>
    </Routes>
  );
}
