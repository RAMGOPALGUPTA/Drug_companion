import React, { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { analyzeImage } from '../services/api.js'
import { pipelineLabels } from '../data/demoData.js'

const demoChoices = [
  ['positive_style.jpg', 'Positive demo'],
  ['negative_style.jpg', 'Negative demo'],
  ['poor_lighting.jpg', 'Poor lighting'],
  ['blurred.jpg', 'Blurred'],
]

function Meter({ value }) { return <div className="meter"><span style={{width:`${Math.round(value*100)}%`}} /></div> }

export function NewTest() {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [pipelineStep, setPipelineStep] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const stage = useMemo(() => pipelineLabels[Math.min(pipelineStep, pipelineLabels.length-1)], [pipelineStep])

  function selectFile(next) {
    if (!next) return
    setFile(next)
    setPreview(URL.createObjectURL(next))
    setResult(null)
    setError('')
  }

  async function runAnalysis() {
    if (!file) return
    setBusy(true); setResult(null); setError('')
    for (let i=0; i<pipelineLabels.length; i += 1) {
      setPipelineStep(i)
      await new Promise(r => setTimeout(r, 220))
    }
    try { setResult(await analyzeImage(file)) } catch (e) { setError(e.message || 'Unable to analyze image') }
    setBusy(false)
  }

  const current = result?.result || 'invalid'
  return <div className="capture-page">
    <div className="capture-intro">
      <div><div className="panel-eyebrow">CAPTURE LANE / STEP 1</div><h2>Bring the strip into the frame.</h2><p>Place the reference card and test strip together. The backend pipeline will normalize the image before model inference.</p></div>
      <div className="capture-contract"><span>MODEL CONTRACT</span><strong>224 × 224</strong><small>RGB · 0–1 normalize · 3 classes</small></div>
    </div>

    <div className="capture-grid">
      <section className="panel upload-panel">
        <div className={`dropzone ${preview ? 'has-preview' : ''}`} onClick={() => inputRef.current?.click()} onDragOver={(e)=>e.preventDefault()} onDrop={(e)=>{e.preventDefault(); selectFile(e.dataTransfer.files?.[0])}}>
          {preview ? <img src={preview} alt="Selected test strip" /> : <div className="empty-capture"><div className="capture-target"><span>+</span></div><strong>Drop a field image here</strong><span>or tap to browse</span><small>JPG · PNG · max 12MB</small></div>}
          {preview && <div className="preview-overlay"><span>FIELD IMAGE</span><b>{file?.name}</b></div>}
        </div>
        <input ref={inputRef} type="file" accept="image/*" hidden onChange={(e)=>selectFile(e.target.files?.[0])} />
        <div className="demo-row"><span className="demo-label">DEMO FIXTURES</span>{demoChoices.map(([name,label]) => <button className="demo-chip" key={name} onClick={()=>fetch(`/demo-images/${name}`).then(r=>r.blob()).then(blob=>selectFile(new File([blob], name, {type:blob.type})))}>{label}</button>)}</div>
      </section>

      <section className="panel process-panel">
        <div className="panel-head"><div><div className="panel-eyebrow">ANALYSIS PIPELINE</div><h2>{busy ? stage[1] : result ? 'Pipeline complete' : 'Standing by'}</h2></div>{busy ? <span className="live-tag">LIVE</span> : <span className="idle-tag">IDLE</span>}</div>
        <div className="pipeline-list">{pipelineLabels.map(([n,label], idx)=><div key={n} className={`pipeline-item ${busy && idx===pipelineStep ? 'active':''} ${result || idx<pipelineStep ? 'done':''}`}><span>{n}</span><div><strong>{label}</strong><small>{idx===0?'Blur / exposure / framing':idx===1?'Reference card normalization':idx===2?'Strip region extraction':idx===3?'CIEDE2000 comparison':idx===4?'ML corroboration':'Hash + provenance'}</small></div><i>{result || idx<pipelineStep ? '✓' : busy && idx===pipelineStep ? '…' : '—'}</i></div>)}</div>
        {busy && <div className="running-line"><span>RUNNING</span><Meter value={(pipelineStep+1)/pipelineLabels.length}/><em>stage {pipelineStep+1}/6</em></div>}
        <div className="process-foot"><button className="primary-button" disabled={!file || busy} onClick={runAnalysis}>{busy ? 'Processing…' : 'Analyze field image ↗'}</button><span>Demo mode: {String(import.meta.env.VITE_DEMO_MODE ?? 'true')}</span></div>
      </section>
    </div>

    {error && <div className="error-banner">{error}</div>}
    {result && <section className={`result-banner ${current}`}>
      <div className="result-main"><div className="result-kicker">MODEL OUTPUT / {result.case_id}</div><div className="result-word">{current === 'invalid' ? 'INCONCLUSIVE' : current.toUpperCase()}</div><div className="result-meta">{Math.round(result.confidence*100)}% confidence · {result.model.name} · {result.model.version}</div></div>
      <div className="result-side"><div><span>IMAGE QUALITY</span><strong>{result.pipeline.image_quality.passed ? 'PASS' : 'REVIEW'}</strong></div><div><span>CALIBRATION</span><strong>{result.pipeline.calibration.passed ? 'PASS' : 'REVIEW'}</strong></div><div><span>ROI</span><strong>{result.pipeline.roi.detected ? 'DETECTED' : 'REVIEW'}</strong></div><Link to={`/cases/${result.case_id}`} className="result-link">Open dossier →</Link></div>
    </section>}
  </div>
}
