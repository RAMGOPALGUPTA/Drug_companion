import React from "react";
import { Link } from "react-router-dom";
import { demoCases, trendData } from "../data/demoData.js";

function ResultPill({ result }) {
  const label = result === "invalid" ? "INCONCLUSIVE" : result.toUpperCase();
  return <span className={`result-pill ${result}`}>{label}</span>;
}

export function Dashboard() {
  const total = 128;
  const positive = 39;
  const negative = 76;
  const inconclusive = 13;
  const max = Math.max(...trendData.map((d) => d.p + d.n + d.i));
  return (
    <div className="page-stack">
      <section className="hero-grid">
        <div className="hero-card">
          <div className="hero-kicker">FIELD TEST / ACTIVE WINDOW</div>
          <div className="hero-title">
            Turn a strip
            <br />
            <em>into a trace.</em>
          </div>
          <p>
            Capture a field test, push it through the visual pipeline, and leave
            every decision attached to a verifiable evidence trail.
          </p>
          <Link className="hero-action" to="/new-test">
            Open capture lane <span>↗</span>
          </Link>
          <div className="hero-orbit orbit-one" />
          <div className="hero-orbit orbit-two" />
        </div>
        <div className="metric-rail">
          <div className="metric-card">
            <div className="metric-label">TESTS / 7 DAYS</div>
            <div className="metric-value">128</div>
            <div className="metric-foot up">+14.6% vs prior window</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">POSITIVE</div>
            <div className="metric-value amber">39</div>
            <div className="metric-foot">30.5% of all calls</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">INCONCLUSIVE</div>
            <div className="metric-value violet">13</div>
            <div className="metric-foot">4 need review</div>
          </div>
        </div>
      </section>

      <section className="content-grid two-col">
        <div className="panel large-panel">
          <div className="panel-head">
            <div>
              <div className="panel-eyebrow">THROUGHPUT / RECENT</div>
              <h2>Signal volume</h2>
            </div>
            <span className="panel-note">18–24 Sep</span>
          </div>
          <div className="signal-chart">
            <div className="chart-y">30</div>
            <div className="chart-y y2">20</div>
            <div className="chart-y y3">10</div>
            <div className="bars">
              {trendData.map((d) => {
                const h = ((d.p + d.n + d.i) / max) * 100;
                return (
                  <div className="bar-column" key={d.day}>
                    <div className="bar-stack" style={{ height: `${h}%` }}>
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
            <span>
              <i className="legend-p" /> Positive
            </span>
            <span>
              <i className="legend-n" /> Negative
            </span>
            <span>
              <i className="legend-i" /> Inconclusive
            </span>
          </div>
        </div>

        <div className="panel dossier-panel">
          <div className="panel-head">
            <div>
              <div className="panel-eyebrow">FIELD STATUS</div>
              <h2>Evidence health</h2>
            </div>
            <span className="verified-badge">97.1%</span>
          </div>
          <div className="health-ring">
            <div>
              <strong>97</strong>
              <span>HEALTH</span>
            </div>
          </div>
          <div className="health-lines">
            <div>
              <span>Hashes sealed</span>
              <strong>124 / 128</strong>
            </div>
            <div>
              <span>Synced cases</span>
              <strong>121 / 128</strong>
            </div>
            <div>
              <span>Review queue</span>
              <strong>04</strong>
            </div>
          </div>
          <Link className="text-link" to="/evidence">
            Inspect evidence ledger →
          </Link>
        </div>
      </section>

      <section className="panel table-panel">
        <div className="panel-head">
          <div>
            <div className="panel-eyebrow">LATEST FIELD ACTIVITY</div>
            <h2>Case stream</h2>
          </div>
          <Link className="text-link" to="/cases">
            View archive →
          </Link>
        </div>
        <div className="case-table">
          <div className="case-row header">
            <span>CASE</span>
            <span>RESULT</span>
            <span>CONFIDENCE</span>
            <span>OFFICER</span>
            <span>LOCATION</span>
            <span>INTEGRITY</span>
          </div>
          {demoCases.slice(0, 4).map((c) => (
            <Link to={`/cases/${c.id}`} className="case-row" key={c.id}>
              <span className="case-id">{c.id}</span>
              <span>
                <ResultPill result={c.result} />
              </span>
              <span className="confidence">
                {Math.round(c.confidence * 100)}%
              </span>
              <span>{c.officer}</span>
              <span>{c.location}</span>
              <span className={`integrity ${c.integrity}`}>
                {c.integrity === "verified" ? "✓ verified" : "△ review"}
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className="mini-strip">
        <span>{total} cases logged</span>
        <b>·</b>
        <span>{positive} positive</span>
        <b>·</b>
        <span>{negative} negative</span>
        <b>·</b>
        <span>{inconclusive} inconclusive</span>
        <div className="mini-strip-fill" />
      </section>
    </div>
  );
}
