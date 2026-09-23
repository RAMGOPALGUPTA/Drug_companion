import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getCases, getCasesSummary, getModelInfo, getStorageStatus } from "../services/api.js";

function ResultPill({ result }) {
  const label = result === "inconclusive" ? "INCONCLUSIVE" : String(result || "").toUpperCase();
  return <span className={"result-pill " + result}>{label}</span>;
}

function dayKey(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString().slice(0, 10);
}

export function Dashboard() {
  const [summary, setSummary] = useState({ total_cases: 0, positive: 0, negative: 0, inconclusive: 0 });
  const [cases, setCases] = useState([]);
  const [model, setModel] = useState(null);
  const [storage, setStorage] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getCasesSummary(), getCases(), getModelInfo(), getStorageStatus()])
      .then(([nextSummary, nextCases, nextModel, nextStorage]) => {
        setSummary(nextSummary);
        setCases(nextCases);
        setModel(nextModel);
        setStorage(nextStorage);
      })
      .catch((e) => setError(e.message || "Unable to load live dashboard"));
  }, []);

  const recentCases = cases.slice(0, 4);
  const trend = useMemo(() => {
    const now = new Date();
    const buckets = [];
    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date(now);
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      buckets.push({
        day: d.toLocaleDateString(undefined, { day: "2-digit" }),
        p: 0,
        n: 0,
        i: 0,
        key,
      });
    }
    const map = new Map(buckets.map((x) => [x.key, x]));
    cases.forEach((item) => {
      const bucket = map.get(dayKey(item.time));
      if (!bucket) return;
      if (item.result === "positive") bucket.p += 1;
      else if (item.result === "negative") bucket.n += 1;
      else bucket.i += 1;
    });
    return buckets;
  }, [cases]);

  const max = Math.max(1, ...trend.map((d) => d.p + d.n + d.i));

  return (
    <div className="page-stack">
      {error && <div className="error-banner">{error}</div>}

      <section className="hero-grid">
        <div className="hero-card">
          <div className="hero-kicker">LIVE BACKEND / ACTIVE WINDOW</div>
          <div className="hero-title">Turn a strip<br /><em>into a trace.</em></div>
          <p>
            Capture a field test, run the live inference pipeline, and leave
            every completed decision attached to a verifiable evidence trail.
          </p>
          <Link className="hero-action" to="/new-test">Open capture lane <span>↗</span></Link>
          <div className="hero-orbit orbit-one" />
          <div className="hero-orbit orbit-two" />
        </div>

        <div className="metric-rail">
          <div className="metric-card">
            <div className="metric-label">PERSISTED CASES</div>
            <div className="metric-value">{summary.total_cases || 0}</div>
            <div className="metric-foot">PostgreSQL-backed archive</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">POSITIVE</div>
            <div className="metric-value amber">{summary.positive || 0}</div>
            <div className="metric-foot">Live backend classification</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">INCONCLUSIVE</div>
            <div className="metric-value violet">{summary.inconclusive || 0}</div>
            <div className="metric-foot">Requires review</div>
          </div>
        </div>
      </section>

      <section className="content-grid two-col">
        <div className="panel large-panel">
          <div className="panel-head">
            <div><div className="panel-eyebrow">THROUGHPUT / RECENT</div><h2>Signal volume</h2></div>
            <span className="panel-note">Last 7 days</span>
          </div>
          <div className="signal-chart">
            <div className="chart-y">MAX</div>
            <div className="bars">
              {trend.map((d) => {
                const h = ((d.p + d.n + d.i) / max) * 100;
                return (
                  <div className="bar-column" key={d.key}>
                    <div className="bar-stack" style={{ height: h + "%" }}>
                      <i style={{ flex: d.p }} />
                      <i style={{ flex: d.n }} />
                      <i style={{ flex: d.i }} />
                    </div>
                    <span>{d.day}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="legend">
            <span><i className="legend-p" /> Positive</span>
            <span><i className="legend-n" /> Negative</span>
            <span><i className="legend-i" /> Inconclusive</span>
          </div>
        </div>

        <div className="panel dossier-panel">
          <div className="panel-head">
            <div><div className="panel-eyebrow">RUNTIME STATUS</div><h2>Evidence health</h2></div>
            <span className="verified-badge">{storage?.database_available ? "ONLINE" : "DEGRADED"}</span>
          </div>
          <div className="health-ring">
            <div><strong>{model?.model_available ? "ON" : "OFF"}</strong><span>MODEL</span></div>
          </div>
          <div className="health-lines">
            <div><span>LiteRT model</span><strong>{model?.model_available ? "READY" : "UNAVAILABLE"}</strong></div>
            <div><span>PostgreSQL</span><strong>{storage?.database_available ? "CONNECTED" : "OFFLINE"}</strong></div>
            <div><span>Validation</span><strong>{model?.target_validated ? "TARGET" : "BOOTSTRAP"}</strong></div>
          </div>
          <Link className="text-link" to="/evidence">Inspect evidence ledger →</Link>
        </div>
      </section>

      <section className="panel table-panel">
        <div className="panel-head">
          <div><div className="panel-eyebrow">LATEST FIELD ACTIVITY</div><h2>Case stream</h2></div>
          <Link className="text-link" to="/cases">View archive →</Link>
        </div>
        <div className="case-table">
          <div className="case-row header">
            <span>CASE</span><span>RESULT</span><span>CONFIDENCE</span><span>OFFICER</span><span>LOCATION</span><span>INTEGRITY</span>
          </div>
          {recentCases.length === 0 && <div className="empty-state">No live cases yet. Run a field image through the capture lane.</div>}
          {recentCases.map((c) => (
            <Link to={"/cases/" + (c.id || c.case_id)} className="case-row" key={c.id || c.case_id}>
              <span className="case-id">{c.id || c.case_id}</span>
              <span><ResultPill result={c.result} /></span>
              <span className="confidence">{Math.round(Number(c.confidence || 0) * 100)}%</span>
              <span>{c.officer || "—"}</span>
              <span>{c.location || "Field capture"}</span>
              <span className={"integrity " + (c.integrity || "review")}>{c.integrity === "verified" ? "✓ verified" : "△ review"}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="mini-strip">
        <span>{summary.total_cases || 0} cases logged</span><b>·</b>
        <span>{summary.positive || 0} positive</span><b>·</b>
        <span>{summary.negative || 0} negative</span><b>·</b>
        <span>{summary.inconclusive || 0} inconclusive</span>
        <div className="mini-strip-fill" />
      </section>
    </div>
  );
}
