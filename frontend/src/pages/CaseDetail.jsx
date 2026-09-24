import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCase, verifyCaseEvidence, downloadCaseReport } from "../services/api.js";

function statusLabel(result) {
  return result === "inconclusive" ? "INCONCLUSIVE" : String(result || "unknown").toUpperCase();
}

function Stage({ number, label, value }) {
  return (
    <div>
      <span>{number}</span>
      <p>{label} <strong>{value}</strong></p>
    </div>
  );
}

export function CaseDetail() {
  const { caseId } = useParams();
  const [c, setCase] = useState(null);
  const [verification, setVerification] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reporting, setReporting] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const record = await getCase(caseId);
        const verified = await verifyCaseEvidence(caseId);
        if (active) {
          setCase(record);
          setVerification(verified);
        }
      } catch (e) {
        if (active) setError(e.message || "Unable to load case");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [caseId]);

  const packet = c?.evidence_packet || {};
  const stages = packet.stages || {};
  const model = c?.model || stages.device_metadata?.model || {};
  const qualityPassed = Boolean(c?.quality?.passed);
  const calibrationPassed = Boolean(c?.calibration?.passed);
  const roiDetected = Boolean(c?.deltae && Object.keys(c.deltae).length);
  const evidenceState = verification?.valid === true ? "verified" : verification ? "review" : "checking";
  const mlValues = useMemo(() => Object.values(c?.ml || {}).filter((x) => x && typeof x === "object"), [c]);

  async function generateReport() {
    setReporting(true);
    try { await downloadCaseReport(caseId); } catch (e) { setError(e.message || "Unable to generate report"); } finally { setReporting(false); }
  }

  if (loading) return <div className="page-stack"><div className="panel empty-state">Loading case dossier…</div></div>;
  if (error || !c) return (
    <div className="page-stack">
      <div className="error-banner">{error || "Case not found"}</div>
      <Link to="/cases" className="text-link">← Back to archive</Link>
    </div>
  );

  return (
    <div className="page-stack">
      <div className="backline"><Link to="/cases">← Back to archive</Link><span>{c.case_id} / evidence dossier</span></div>

      <section className="dossier-grid">
        <div className="panel image-dossier">
          <div className="panel-eyebrow">ORIGINAL CAPTURE / HASH-REFERENCED</div>
          <div className="dossier-image dossier-placeholder">
            <div>
              <strong>Image bytes are sealed server-side.</strong>
              <span>{c.filename || "Uploaded field image"}</span>
              <code>{c.evidence?.image_sha256 || "hash unavailable"}</code>
            </div>
            <span>READ-ONLY EVIDENCE REFERENCE</span>
          </div>
          <div className="image-caption"><span>{c.location || "Field capture"}</span><span>{c.time || packet.created_utc || "timestamp unavailable"}</span></div>
        </div>

        <div className="panel case-summary">
          <div className="summary-top">
            <div>
              <div className="panel-eyebrow">CASE {c.case_id}</div>
              <h2>{statusLabel(c.result)}</h2>
              <p>Model confidence <strong>{Math.round(Number(c.confidence || 0) * 100)}%</strong></p>
            </div>
            <div className="case-summary-actions"><button className="secondary-button" type="button" onClick={generateReport} disabled={reporting}>{reporting ? "Generating…" : "Generate PDF"}</button><div className={"result-orb " + c.result}>{Math.round(Number(c.confidence || 0) * 100)}<small>%</small></div></div>
          </div>
          <div className="detail-grid">
            <div><span>OFFICER</span><strong>{c.officer || "—"}</strong></div>
            <div><span>MODEL</span><strong>{model.name || "—"}</strong></div>
            <div><span>LOCATION</span><strong>{c.location || "Field capture"}</strong></div>
            <div><span>CAPTURED</span><strong>{c.time || packet.created_utc || "—"}</strong></div>
            <div><span>MODEL STATUS</span><strong>{model.target_validated ? "TARGET VALIDATED" : "BOOTSTRAP / DEMO"}</strong></div>
            <div><span>STORAGE</span><strong>{c.storage || "—"}</strong></div>
          </div>
          <div className="seal-box">
            <div><div className="seal-check">{evidenceState === "verified" ? "✓" : "△"}</div><div><span>Evidence integrity</span><strong>{evidenceState.toUpperCase()}</strong></div></div>
            <code>{c.evidence?.payload_sha256 || "hash unavailable"}</code>
            <Link to="/evidence">Inspect ledger →</Link>
          </div>
        </div>
      </section>

      <section className="content-grid two-col">
        <div className="panel">
          <div className="panel-eyebrow">DECISION TRACE</div><h2>Live pipeline record</h2>
          <div className="trace-list">
            <Stage number="01" label="Image quality gate" value={qualityPassed ? "PASS" : "REVIEW"} />
            <Stage number="02" label="Reference normalization" value={calibrationPassed ? "COMPLETE" : "REVIEW"} />
            <Stage number="03" label="ROI extraction" value={roiDetected ? "DETECTED" : "REVIEW"} />
            <Stage number="04" label="Rule engine" value={c.result === "inconclusive" ? "INCONCLUSIVE" : "COMPLETED"} />
            <Stage number="05" label="ML corroboration" value={mlValues.length + " analyte outputs"} />
            <Stage number="06" label="Evidence seal" value={evidenceState.toUpperCase()} />
          </div>
        </div>
        <div className="panel note-panel">
          <div className="panel-eyebrow">MODEL STATUS</div><h2>{model.name || "MobileNetV3-Small"}</h2>
          <p>This software path is connected to the live LiteRT model artifact. The artifact remains explicitly classified as a bootstrap/demo model until target-data validation is completed.</p>
          <div className="note-tag">{model.forensic_status || "PROTOTYPE_DEMO_ONLY_NOT_FORENSICALLY_VALIDATED"}</div>
        </div>
      </section>

      <section className="content-grid two-col">
        <div className="panel"><div className="panel-eyebrow">RULE ENGINE OUTPUT</div><h2>Analyte calls</h2><pre className="json-block">{JSON.stringify(c.deltae || {}, null, 2)}</pre></div>
        <div className="panel"><div className="panel-eyebrow">ARBITRATION OUTPUT</div><h2>Final per-analyte decisions</h2><pre className="json-block">{JSON.stringify(c.resolved || {}, null, 2)}</pre></div>
      </section>
    </div>
  );
}