import { Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { Audit } from './pages/Audit';
import { Dashboard } from './pages/Dashboard';
import { GuardrailsPanel } from './pages/GuardrailsPanel';
import { Onboarding } from './pages/Onboarding';
import { Portfolio } from './pages/Portfolio';
import { Settings } from './pages/Settings';

export default function App() {
  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <TopBar />
        <div className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/guardrails" element={<GuardrailsPanel />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/onboarding" element={<Onboarding />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
