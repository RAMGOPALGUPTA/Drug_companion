import React from "react";
import { trendData } from "../data/demoData.js";
export function Analytics() {
  const totals = trendData.reduce(
    (a, d) => ({ p: a.p + d.p, n: a.n + d.n, i: a.i + d.i }),
    { p: 0, n: 0, i: 0 },
  );
  const total = totals.p + totals.n + totals.i;
  return (
    <div className="page-stack">
      <section className="signal-hero">
        <div>
          <div className="panel-eyebrow">OPERATIONS / 7-DAY WINDOW</div>
          <h2>
            Find the signal
            <br />
            <em>between the cases.</em>
          </h2>
        </div>
        <div className="big-number">
          <strong>{total}</strong>
          <span>field calls</span>
        </div>
      </section>
      <section className="content-grid three-col">
        <div className="panel">
          <div className="panel-eyebrow">POSITIVE</div>
          <div className="analytic-number amber">{totals.p}</div>
          <div className="micro-copy">
            {Math.round((totals.p / total) * 100)}% of recorded calls
          </div>
        </div>
        <div className="panel">
          <div className="panel-eyebrow">NEGATIVE</div>
          <div className="analytic-number">{totals.n}</div>
          <div className="micro-copy">
            {Math.round((totals.n / total) * 100)}% of recorded calls
          </div>
        </div>
        <div className="panel">
          <div className="panel-eyebrow">INCONCLUSIVE</div>
          <div className="analytic-number violet">{totals.i}</div>
          <div className="micro-copy">
            {Math.round((totals.i / total) * 100)}% need human review
          </div>
        </div>
      </section>
      <section className="panel analytics-chart">
        <div className="panel-head">
          <div>
            <div className="panel-eyebrow">DAILY VOLUME</div>
            <h2>Case density</h2>
          </div>
          <span className="panel-note">Last 7 days</span>
        </div>
        <div className="line-chart">
          {trendData.map((d, i) => (
            <div className="line-day" key={d.day}>
              <div
                className="line-total"
                style={{ height: `${((d.p + d.n + d.i) / 30) * 100}%` }}
              >
                <i style={{ height: `${(d.p / (d.p + d.n + d.i)) * 100}%` }} />
                <i style={{ height: `${(d.n / (d.p + d.n + d.i)) * 100}%` }} />
                <i style={{ height: `${(d.i / (d.p + d.n + d.i)) * 100}%` }} />
              </div>
              <span>{d.day}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
