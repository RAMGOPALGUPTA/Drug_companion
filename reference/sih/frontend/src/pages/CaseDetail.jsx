import React from 'react'
import { Link, useParams } from 'react-router-dom'
import { demoCases } from '../data/demoData.js'

export function CaseDetail() {
  const { caseId } = useParams()
  const c = demoCases.find(x=>x.id===caseId) || demoCases[0]
  const result = c.result === 'invalid' ? 'INCONCLUSIVE' : c.result.toUpperCase()
  const hash = '8e91c4bf0a1ed3b9…c74a72'
  return <div className="page-stack">
    <div className="backline"><Link to="/cases">← Back to archive</Link><span>{c.id} / evidence dossier</span></div>
    <section className="dossier-grid">
      <div className="panel image-dossier"><div className="panel-eyebrow">ORIGINAL CAPTURE</div><div className="dossier-image"><img src={c.image} alt="Field strip" /><span>ORIGINAL / READ-ONLY</span></div><div className="image-caption"><span>{c.location}</span><span>{c.time} · 24 SEP 2026</span></div></div>
      <div className="panel case-summary"><div className="summary-top"><div><div className="panel-eyebrow">CASE {c.id}</div><h2>{result}</h2><p>Model confidence <strong>{Math.round(c.confidence*100)}%</strong></p></div><div className={`result-orb ${c.result}`}>{Math.round(c.confidence*100)}<small>%</small></div></div>
        <div className="detail-grid"><div><span>OFFICER</span><strong>{c.officer}</strong></div><div><span>MODEL</span><strong>MobileNetV3-Small</strong></div><div><span>LOCATION</span><strong>{c.location}</strong></div><div><span>CAPTURED</span><strong>24 Sep 2026 · {c.time}</strong></div><div><span>GPS</span><strong>30.7046° N · 76.7179° E</strong></div><div><span>RULE PATH</span><strong>{c.result==='invalid'?'Inconclusive':'Delta-E confident'}</strong></div></div>
        <div className="seal-box"><div><div className="seal-check">✓</div><div><span>Evidence integrity</span><strong>Verified</strong></div></div><code>{hash}</code><Link to="/evidence">Inspect seal →</Link></div>
      </div>
    </section>
    <section className="content-grid two-col"><div className="panel"><div className="panel-eyebrow">DECISION TRACE</div><h2>Why this result reads the way it does</h2><div className="trace-list"><div><span>01</span><p>Image quality gate <strong>PASS</strong></p></div><div><span>02</span><p>Reference normalization <strong>COMPLETE</strong></p></div><div><span>03</span><p>ROI extraction <strong>DETECTED</strong></p></div><div><span>04</span><p>Rule engine <strong>{c.result==='invalid'?'INCONCLUSIVE':'CONFIDENT'}</strong></p></div><div><span>05</span><p>ML signal <strong>{Math.round(c.confidence*100)}%</strong></p></div></div></div><div className="panel note-panel"><div className="panel-eyebrow">OPERATING NOTE</div><h2>Prototype status</h2><p>This dossier is a prototype demonstration using synthetic demo fixtures. The classifier output is advisory and should not be presented as forensic validation.</p><div className="note-tag">SYNTHETIC DEMO / NOT FORENSICALLY VALIDATED</div></div></section>
  </div>
}
