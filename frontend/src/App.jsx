import React, { useEffect, useMemo, useState } from "react";
import {
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Dashboard } from "./pages/Dashboard.jsx";
import { NewTest } from "./pages/NewTest.jsx";
import { Cases } from "./pages/Cases.jsx";
import { CaseDetail } from "./pages/CaseDetail.jsx";
import { Evidence } from "./pages/Evidence.jsx";
import { Analytics } from "./pages/Analytics.jsx";
import { getModelInfo, getStorageStatus } from "./services/api.js";

function Glyph({ type, size = 18 }) {
  const paths = {
    grid: "M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z",
    scan: "M7 3H5a2 2 0 0 0-2 2v2 M17 3h2a2 2 0 0 1 2 2v2 M7 21H5a2 2 0 0 1-2-2v-2 M17 21h2a2 2 0 0 0 2-2v-2 M8 8h8v8H8z",
    cases: "M4 7h16v12H4z M7 7V5h10v2",
    shield: "M12 3l7 3v6c0 4.6-3 7.8-7 9-4-1.2-7-4.4-7-9V6z M9 12l2 2 4-4",
    chart: "M4 19V5 M4 19h17 M8 15l3-4 3 2 5-7",
    user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21a8 8 0 0 1 16 0",
    gear: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M3 12h2m14 0h2M12 3v2m0 14v2M5.6 5.6L7 7m10 10 1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4",
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[type] || paths.grid} />
    </svg>
  );
}

function Shell({ children }) {
  const location = useLocation();
  const [runtime, setRuntime] = useState({ model: false, database: false });

  useEffect(() => {
    Promise.all([getModelInfo(), getStorageStatus()])
      .then(([model, storage]) => setRuntime({ model: model.model_available, database: storage.database_available }))
      .catch(() => setRuntime({ model: false, database: false }));
  }, []);
  const navigate = useNavigate();
  const title = useMemo(() => {
    if (location.pathname.startsWith("/new-test"))
      return ["New field test", "Capture → interpret → seal"];
    if (location.pathname.startsWith("/cases/"))
      return ["Case dossier", "Evidence-grade record"];
    if (location.pathname.startsWith("/cases"))
      return ["Case archive", "Every test. One chain of custody."];
    if (location.pathname.startsWith("/evidence"))
      return ["Evidence integrity", "Hashes, provenance, verification"];
    if (location.pathname.startsWith("/analytics"))
      return ["Signal room", "Read the operation at a glance"];
    return ["Field Evidence Console", "SIH26231 · Digital Companion"];
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">FE</div>
          <div>
            <div className="brand-name">Field Evidence</div>
            <div className="brand-sub">SIH26231 / CONSOLE</div>
          </div>
        </div>

        <div className="side-section-label">OPERATIONS</div>
        <nav className="nav-list">
          <NavLink className="nav-item" to="/">
            <Glyph type="grid" />
            <span>Overview</span>
            <kbd>01</kbd>
          </NavLink>
          <NavLink className="nav-item" to="/new-test">
            <Glyph type="scan" />
            <span>New Test</span>
            <kbd>02</kbd>
          </NavLink>
          <NavLink className="nav-item" to="/cases">
            <Glyph type="cases" />
            <span>Case Archive</span>
            <kbd>03</kbd>
          </NavLink>
          <NavLink className="nav-item" to="/evidence">
            <Glyph type="shield" />
            <span>Evidence</span>
            <kbd>04</kbd>
          </NavLink>
          <NavLink className="nav-item" to="/analytics">
            <Glyph type="chart" />
            <span>Signal Room</span>
            <kbd>05</kbd>
          </NavLink>
        </nav>

        <div className="sidebar-spacer" />
        <div className="connection-card">
          <div className="pulse-dot" />
          <div>
            <div className="connection-title">Prototype online</div>
            <div className="connection-copy">Inference gateway armed</div>
          </div>
        </div>
        <button className="operator-button" onClick={() => navigate("/")}>
          <div className="operator-avatar">RG</div>
          <div className="operator-meta">
            <strong>Ram Gupta</strong>
            <span>Field Officer · A-17</span>
          </div>
          <Glyph type="gear" size={17} />
        </button>
      </aside>

      <main className="main-canvas">
        <header className="topbar">
          <div>
            <div className="eyebrow">{title[1]}</div>
            <h1>{title[0]}</h1>
          </div>
          <div className="topbar-actions">
            <div className="status-chip">
              <span className="chip-dot" /> {runtime.model && runtime.database ? "API READY" : "API DEGRADED"}
            </div>
            <button
              className="quick-capture"
              onClick={() => navigate("/new-test")}
            >
              <Glyph type="scan" size={16} /> Start test
            </button>
          </div>
        </header>
        {children}
        <footer className="footer-line">
          <span>Prototype environment · Live backend data</span>
          <span>MODEL / MobileNetV3-Small · 224×224 RGB · bootstrap</span>
        </footer>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/new-test" element={<NewTest />} />
        <Route path="/cases" element={<Cases />} />
        <Route path="/cases/:caseId" element={<CaseDetail />} />
        <Route path="/evidence" element={<Evidence />} />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </Shell>
  );
}
