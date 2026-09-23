import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { demoCases } from "../data/demoData.js";
import { getCases } from "../services/api.js";

const labels = {
  positive: "POSITIVE",
  negative: "NEGATIVE",
  invalid: "INCONCLUSIVE",
};
export function Cases() {
  const [cases, setCases] = useState(demoCases);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  useEffect(() => {
    getCases()
      .then(setCases)
      .catch(() => {});
  }, []);
  const visible = useMemo(
    () =>
      cases.filter(
        (c) =>
          (filter === "all" || c.result === filter) &&
          `${c.id} ${c.officer} ${c.location}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [cases, query, filter],
  );
  return (
    <div className="page-stack">
      <section className="panel archive-toolbar">
        <div>
          <div className="panel-eyebrow">CHAIN OF CUSTODY / ARCHIVE</div>
          <h2>{visible.length} visible cases</h2>
        </div>
        <div className="toolbar-controls">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search case, officer, location"
          />
          <div className="filter-group">
            {["all", "positive", "negative", "invalid"].map((x) => (
              <button
                key={x}
                className={filter === x ? "selected" : ""}
                onClick={() => setFilter(x)}
              >
                {x === "invalid" ? "inconclusive" : x}
              </button>
            ))}
          </div>
        </div>
      </section>
      <section className="panel table-panel">
        <div className="case-table wide">
          <div className="case-row header">
            <span>CASE</span>
            <span>RESULT</span>
            <span>CONFIDENCE</span>
            <span>OFFICER</span>
            <span>LOCATION</span>
            <span>INTEGRITY</span>
          </div>
          {visible.map((c) => (
            <Link className="case-row" key={c.id} to={`/cases/${c.id}`}>
              <span className="case-id">{c.id}</span>
              <span>
                <span className={`result-pill ${c.result}`}>
                  {labels[c.result]}
                </span>
              </span>
              <span className="confidence">
                {Math.round(c.confidence * 100)}%
              </span>
              <span>{c.officer}</span>
              <span>
                {c.location}
                <small className="row-time">{c.time}</small>
              </span>
              <span className={`integrity ${c.integrity}`}>
                {c.integrity === "verified" ? "✓ verified" : "△ review"}
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
