import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCases, verifyCaseEvidence } from "../services/api.js";

function shortHash(value) {
  if (!value) return "—";
  return value.length > 18 ? value.slice(0, 10) + "…" + value.slice(-8) : value;
}

export function Evidence() {
  const [cases, setCases] = useState([]);
  const [verification, setVerification] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const rows = await getCases();
        setCases(rows);
        const checks = await Promise.all(
          rows.slice(0, 10).map(async (row) => {
            try {
              return [row.case_id || row.id, await verifyCaseEvidence(row.case_id || row.id)];
            } catch {
              return [row.case_id || row.id, { valid: false }];
            }
          }),
        );
        setVerification(Object.fromEntries(checks));
      } catch (e) {
        setError(e.message || "Unable to load evidence ledger");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const verifiedCount = Object.values(verification).filter((x) => x.valid).length;

  return (
    <div className="page-stack">
      <section className="evidence-hero">
        <div>
          <div className="panel-eyebrow">EVIDENCE LEDGER</div>
          <h2>Seal the image.<br /><em>Then prove it.</em></h2>
          <p>
            The ledger is backed by the live backend. Each persisted case carries
            an image SHA-256, evidence payload hash, and canonical evidence packet.
          </p>
        </div>
        <div className="ledger-glyph"><div>SHA</div><small>256</small></div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <section className="panel table-panel">
        <div className="panel-head">
          <div>
            <div className="panel-eyebrow">INTEGRITY QUEUE</div>
            <h2>{loading ? "Checking seals…" : "Recent persisted seals"}</h2>
          </div>
          <span className="verified-badge">{verifiedCount} verified</span>
        </div>

        <div className="case-table evidence-table">
          <div className="case-row header">
            <span>CASE</span><span>IMAGE HASH</span><span>PAYLOAD HASH</span><span>STATE</span>
          </div>

          {!loading && cases.length === 0 && <div className="empty-state">No evidence records yet.</div>}

          {cases.slice(0, 10).map((row) => {
            const id = row.case_id || row.id;
            const check = verification[id];
            return (
              <Link className="case-row" key={id} to={"/cases/" + id}>
                <span className="case-id">{id}</span>
                <code>{shortHash(check?.image_sha256)}</code>
                <code>{shortHash(check?.payload_sha256)}</code>
                <span className={"integrity " + (check?.valid ? "verified" : "review")}>
                  {check?.valid ? "✓ verified" : "△ checking"}
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="hash-explainer">
        <div><span>IMAGE</span><strong>JPEG / PNG / WEBP bytes</strong></div>
        <b>→</b><div><span>HASH</span><strong>SHA-256</strong></div>
        <b>→</b><div><span>PAYLOAD</span><strong>Canonical JSON</strong></div>
        <b>→</b><div><span>CHECK</span><strong>Verified / review</strong></div>
      </section>
    </div>
  );
}
