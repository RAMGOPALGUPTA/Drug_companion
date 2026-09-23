import React from 'react'
import { Link } from 'react-router-dom'

const rows = [
  ['CASE-1042','8e91c4bf…c74a72','a31cd882…91fe03','verified'],
  ['CASE-1041','a17f98c1…b4d210','02fe410a…19ac08','verified'],
  ['CASE-1040','f214990a…61d1aa','f214990a…61d1aa','review'],
  ['CASE-1039','b44a2ef2…7e1a8b','6c30d773…4c0d11','verified'],
]
export function Evidence() {
  return <div className="page-stack">
    <section className="evidence-hero"><div><div className="panel-eyebrow">EVIDENCE LEDGER</div><h2>Seal the image.<br /><em>Then prove it.</em></h2><p>Every captured field image can carry a content hash and canonical payload hash. The website surfaces the comparison without exposing private server internals.</p></div><div className="ledger-glyph"><div>SHA</div><small>256</small></div></section>
    <section className="panel table-panel"><div className="panel-head"><div><div className="panel-eyebrow">INTEGRITY QUEUE</div><h2>Recent seals</h2></div><span className="verified-badge">124 verified</span></div><div className="case-table evidence-table"><div className="case-row header"><span>CASE</span><span>IMAGE HASH</span><span>PAYLOAD HASH</span><span>STATE</span></div>{rows.map(r=><Link className="case-row" key={r[0]} to={`/cases/${r[0]}`}><span className="case-id">{r[0]}</span><code>{r[1]}</code><code>{r[2]}</code><span className={`integrity ${r[3]}`}>{r[3]==='verified'?'✓ verified':'△ review'}</span></Link>)}</div></section>
    <section className="hash-explainer"><div><span>IMAGE</span><strong>JPEG bytes</strong></div><b>→</b><div><span>HASH</span><strong>SHA-256</strong></div><b>→</b><div><span>PAYLOAD</span><strong>Canonical JSON</strong></div><b>→</b><div><span>CHECK</span><strong>Match / mismatch</strong></div></section>
  </div>
}
