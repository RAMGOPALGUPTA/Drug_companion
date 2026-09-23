import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { analyzeImage, getModelInfo } from "../services/api.js";
import { pipelineLabels } from "../data/demoData.js";

const MAX_IMAGE_BYTES = 12 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function Meter({ value }) {
  return (
    <div className="meter">
      <span style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

export function NewTest() {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pipelineStep, setPipelineStep] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [model, setModel] = useState(null);
  const [operatorId, setOperatorId] = useState("demo-operator");
  const [location, setLocation] = useState("Field capture");

  const stage = useMemo(
    () => pipelineLabels[Math.min(pipelineStep, pipelineLabels.length - 1)],
    [pipelineStep],
  );

  useEffect(() => {
    getModelInfo().then(setModel).catch(() => {});
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function selectFile(next) {
    if (!next) return;
    setError("");

    if (!ALLOWED_TYPES.has(next.type)) {
      setError("Upload must be JPEG, PNG, or WEBP.");
      return;
    }
    if (next.size > MAX_IMAGE_BYTES) {
      setError("Image exceeds the 12 MB upload limit.");
      return;
    }

    setFile(next);
    setPreview(URL.createObjectURL(next));
    setResult(null);
    setPipelineStep(0);
  }

  async function runAnalysis() {
    if (!file) return;

    setBusy(true);
    setResult(null);
    setError("");

    try {
      for (let i = 0; i < pipelineLabels.length; i += 1) {
        setPipelineStep(i);
        await new Promise((resolve) => setTimeout(resolve, 160));
      }
      const response = await analyzeImage(file, { operatorId, location });
      setResult(response);
      setPipelineStep(pipelineLabels.length - 1);
    } catch (e) {
      setError(e.message || "Unable to analyze image");
    } finally {
      setBusy(false);
    }
  }

  const current = result?.result || "inconclusive";

  return (
    <div className="capture-page">
      <div className="capture-intro">
        <div>
          <div className="panel-eyebrow">CAPTURE LANE / STEP 1</div>
          <h2>Bring the strip into the frame.</h2>
          <p>
            Upload a field image. The live backend runs quality gating,
            calibration, ROI extraction, rule analysis, ML corroboration, and
            evidence sealing.
          </p>
        </div>
        <div className="capture-contract">
          <span>LIVE MODEL CONTRACT</span>
          <strong>{model?.input?.slice(0, 2).join(" × ") || "224 × 224"}</strong>
          <small>
            {model?.normalization || "rescaling_0_to_1"} ·{" "}
            {model?.class_labels?.length || 3} classes
          </small>
        </div>
      </div>

      <div className="capture-grid">
        <section className="panel upload-panel">
          <div
            className={`dropzone ${preview ? "has-preview" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              selectFile(e.dataTransfer.files?.[0]);
            }}
          >
            {preview ? (
              <img src={preview} alt="Selected test strip" />
            ) : (
              <div className="empty-capture">
                <div className="capture-target">
                  <span>+</span>
                </div>
                <strong>Drop a field image here</strong>
                <span>or tap to browse</span>
                <small>JPG · PNG · WEBP · max 12MB</small>
              </div>
            )}
            {preview && (
              <div className="preview-overlay">
                <span>FIELD IMAGE</span>
                <b>{file?.name}</b>
              </div>
            )}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(e) => selectFile(e.target.files?.[0])}
          />

          <div className="capture-fields">
            <label>
              <span>OPERATOR</span>
              <input value={operatorId} onChange={(e) => setOperatorId(e.target.value)} />
            </label>
            <label>
              <span>LOCATION</span>
              <input value={location} onChange={(e) => setLocation(e.target.value)} />
            </label>
          </div>
        </section>

        <section className="panel process-panel">
          <div className="panel-head">
            <div>
              <div className="panel-eyebrow">LIVE ANALYSIS PIPELINE</div>
              <h2>
                {busy ? stage[1] : result ? "Pipeline complete" : "Standing by"}
              </h2>
            </div>
            {busy ? (
              <span className="live-tag">LIVE</span>
            ) : (
              <span className="idle-tag">IDLE</span>
            )}
          </div>

          <div className="pipeline-list">
            {pipelineLabels.map(([n, label], idx) => (
              <div
                key={n}
                className={`pipeline-item ${busy && idx === pipelineStep ? "active" : ""} ${result || idx < pipelineStep ? "done" : ""}`}
              >
                <span>{n}</span>
                <div>
                  <strong>{label}</strong>
                  <small>
                    {idx === 0
                      ? "Blur / exposure / framing"
                      : idx === 1
                        ? "Reference card normalization"
                        : idx === 2
                          ? "Strip region extraction"
                          : idx === 3
                            ? "CIEDE2000 comparison"
                            : idx === 4
                              ? "ML corroboration"
                              : "Hash + provenance"}
                  </small>
                </div>
                <i>
                  {result || idx < pipelineStep
                    ? "✓"
                    : busy && idx === pipelineStep
                      ? "…"
                      : "—"}
                </i>
              </div>
            ))}
          </div>

          {busy && (
            <div className="running-line">
              <span>RUNNING</span>
              <Meter value={(pipelineStep + 1) / pipelineLabels.length} />
              <em>stage {pipelineStep + 1}/6</em>
            </div>
          )}

          <div className="process-foot">
            <button
              className="primary-button"
              disabled={!file || busy}
              onClick={runAnalysis}
            >
              {busy ? "Processing…" : "Analyze field image ↗"}
            </button>
            <span>
              {model?.model_available ? "Backend model online" : "Checking backend model…"}
            </span>
          </div>
        </section>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {result && (
        <section className={`result-banner ${current}`}>
          <div className="result-main">
            <div className="result-kicker">
              LIVE MODEL OUTPUT / {result.case_id}
            </div>
            <div className="result-word">
              {current === "inconclusive" ? "INCONCLUSIVE" : current.toUpperCase()}
            </div>
            <div className="result-meta">
              {Math.round(result.confidence * 100)}% confidence ·{" "}
              {result.model.name} · {result.model.version}
            </div>
            {result.demo_only && (
              <small className="prototype-warning">
                Bootstrap model — prototype output, not forensic validation.
              </small>
            )}
          </div>
          <div className="result-side">
            <div>
              <span>IMAGE QUALITY</span>
              <strong>
                {result.pipeline.image_quality.passed ? "PASS" : "REVIEW"}
              </strong>
            </div>
            <div>
              <span>CALIBRATION</span>
              <strong>
                {result.pipeline.calibration.passed ? "PASS" : "REVIEW"}
              </strong>
            </div>
            <div>
              <span>ROI</span>
              <strong>
                {result.pipeline.roi.detected ? "DETECTED" : "REVIEW"}
              </strong>
            </div>
            <div>
              <span>STORAGE</span>
              <strong>{result.storage === "postgresql" ? "POSTGRESQL" : "MEMORY"}</strong>
            </div>
            <Link to={`/cases/${result.case_id}`} className="result-link">
              Open dossier →
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}
