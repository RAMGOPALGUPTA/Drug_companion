import React, { useEffect, useMemo, useState } from "react";
import { getCases, getCasesSummary } from "../services/api.js";

function dayKey(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString().slice(0, 10);
}

export function Analytics() {
  const [summary, setSummary] = useState({ total_cases: 0, positive: 0, negative: 0, inconclusive: 0 });
  const [cases, setCases] = useState([]);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const [nextSummary, nextCases] = await Promise.all([getCasesSummary(), getCases()]);
        if (!active) return;
        setSummary(nextSummary);
        setCases(nextCases);
        setLastUpdated(new Date());
        setError("");
      } catch (e) {
        if (active) setError(e.message || "Unable to load live analytics");
      }
    }
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const trend = useMemo(() => {
    const now = new Date();
    const buckets = [];
    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date(now);
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - i);
      buckets.push({
        day: d.toLocaleDateString(undefined, { day: "2-digit" }),
        key: d.toISOString().slice(0, 10),
        p: 0,
        n: 0,
        i: 0,
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
  const total = Number(summary.total_cases || 0);

  return (
    <div className="page-stack">
      {error && <div className="error-banner">{error}</div>}

      <section className="signal-hero">
        <div>
          <div className="panel-eyebrow">OPERATIONS / LIVE DATA</div>
          <h2>Find the signal<br /><em>between the cases.</em></h2>
        </div>
        <div className="big-number"><strong>{total}</strong><span>persisted cases</span></div>
      </section>

      <section className="content-grid three-col">
        <div className="panel">
          <div className="panel-eyebrow">POSITIVE</div>
          <div className="analytic-number amber">{summary.positive || 0}</div>
          <div className="micro-copy">{total ? Math.round((summary.positive / total) * 100) : 0}% of persisted cases</div>
        </div>
        <div className="panel">
          <div className="panel-eyebrow">NEGATIVE</div>
          <div className="analytic-number">{summary.negative || 0}</div>
          <div className="micro-copy">{total ? Math.round((summary.negative / total) * 100) : 0}% of persisted cases</div>
        </div>
        <div className="panel">
          <div className="panel-eyebrow">INCONCLUSIVE</div>
          <div className="analytic-number violet">{summary.inconclusive || 0}</div>
          <div className="micro-copy">{total ? Math.round((summary.inconclusive / total) * 100) : 0}% require review</div>
        </div>
      </section>

      <section className="panel analytics-chart">
        <div className="panel-head">
          <div><div className="panel-eyebrow">DAILY VOLUME</div><h2>Case density</h2></div>
          <span className="panel-note">Live · Last 7 days {lastUpdated ? `· ${lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}</span>
        </div>
        <div className="line-chart">
          {trend.map((d) => (
            <div className="line-day" key={d.key}>
              <div className="line-total" style={{ height: ((d.p + d.n + d.i) / max) * 100 + "%" }}>
                <i style={{ height: (d.p / Math.max(1, d.p + d.n + d.i)) * 100 + "%" }} />
                <i style={{ height: (d.n / Math.max(1, d.p + d.n + d.i)) * 100 + "%" }} />
                <i style={{ height: (d.i / Math.max(1, d.p + d.n + d.i)) * 100 + "%" }} />
              </div>
              <span>{d.day}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="analytics-breakdown">
        <div><span>POSITIVE</span><strong>{summary.positive || 0}</strong></div>
        <div><span>NEGATIVE</span><strong>{summary.negative || 0}</strong></div>
        <div><span>INCONCLUSIVE</span><strong>{summary.inconclusive || 0}</strong></div>
        <div><span>DECIDED RATE</span><strong>{total ? Math.round(((Number(summary.positive || 0) + Number(summary.negative || 0)) / total) * 100) : 0}%</strong></div>
      </section>
    </div>
  );
}
