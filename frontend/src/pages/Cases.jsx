import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getCases, downloadCaseReport } from "../services/api.js";

const labels = {
  positive: "POSITIVE",
  negative: "NEGATIVE",
  inconclusive: "INCONCLUSIVE",
};

export function Cases() {
  const [cases, setCases] = useState([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reporting, setReporting] = useState("");

  async function loadCases() {
    setLoading(true);
    setError("");
    try {
      setCases(await getCases());
    } catch (e) {
      setError(e.message || "Unable to load cases");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCases();
  }, []);

  const visible = useMemo(
    () =>
      cases.filter(
        (c) =>
          (filter === "all" || c.result === filter) &&
          `${c.id} ${c.case_id} ${c.officer} ${c.location}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [cases, query, filter],
  );

  async function generateReport(event, caseId) {
    event.preventDefault();
    event.stopPropagation();
    setReporting(caseId);
    try { await downloadCaseReport(caseId); } catch (e) { setError(e.message || "Unable to generate report"); } finally { setReporting(""); }
  }

  return (
    <div className="page-stack">
      <section className="panel archive-toolbar">
        <div>
          <div className="panel-eyebrow">CHAIN OF CUSTODY / ARCHIVE</div>
          <h2>{loading ? "Loading cases…" : `${visible.length} visible cases`}</h2>
        </div>
        <div className="toolbar-controls">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search case, officer, location"
          />
          <div className="filter-group">
            {["all", "positive", "negative", "inconclusive"].map((x) => (
              <button
                key={x}
                className={filter === x ? "selected" : ""}
                onClick={() => setFilter(x)}
              >
                {x}
              </button>
            ))}
          </div>
        </div>
      </section>

      {error && (
        <div className="error-banner">
          {error}
          <button className="text-link" onClick={loadCases}>Retry</button>
        </div>
      )}

      <section className="panel table-panel">
        <div className="case-table wide">
          <div className="case-row header"><span>CASE</span><span>RESULT</span><span>CONFIDENCE</span><span>OFFICER</span><span>LOCATION</span><span>INTEGRITY / REPORT</span></div>

          {!loading && visible.length === 0 && !error && (
            <div className="empty-state">No persisted cases match this view.</div>
          )}

          {visible.map((c) => (
            <Link className="case-row" key={c.id || c.case_id} to={`/cases/${c.id || c.case_id}`}>
              <span className="case-id">{c.id || c.case_id}</span>
              <span>
                <span className={`result-pill ${c.result}`}>
                  {labels[c.result] || String(c.result).toUpperCase()}
                </span>
              </span>
              <span className="confidence">
                {Math.round(Number(c.confidence || 0) * 100)}%
              </span>
              <span>{c.officer || "—"}</span>
              <span>
                {c.location || "Field capture"}
                <small className="row-time">{c.time || ""}</small>
              </span>
              <span className={`integrity ${c.integrity || "review"}`}>{c.integrity === "verified" ? "✓ verified" : "△ review"}</span>
              <button className="row-report-button" onClick={(event) => generateReport(event, c.id || c.case_id)} disabled={reporting === (c.id || c.case_id)}>{reporting === (c.id || c.case_id) ? "…" : "PDF"}</button>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
