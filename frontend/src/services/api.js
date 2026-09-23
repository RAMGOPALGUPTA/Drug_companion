const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8003/api/v1'
const DEMO_MODE = String(import.meta.env.VITE_DEMO_MODE ?? 'true') !== 'false'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function hashLike(seed) {
  let h = 2166136261
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return `${(h >>> 0).toString(16).padStart(8, '0')}${Math.random().toString(16).slice(2, 10)}`.padEnd(64, '7').slice(0, 64)
}

function demoPrediction(file) {
  const name = file?.name?.toLowerCase() || ''
  let result = 'invalid'
  if (name.includes('positive')) result = 'positive'
  else if (name.includes('negative')) result = 'negative'
  else if (name.includes('inconclusive')) result = 'invalid'
  else result = ['positive', 'negative', 'invalid'][Math.floor(Math.random() * 3)]

  const confidence = result === 'invalid' ? 0.61 : 0.84 + Math.random() * 0.11
  return {
    case_id: `CASE-${Math.floor(1000 + Math.random() * 8999)}`,
    result,
    confidence: Number(confidence.toFixed(4)),
    rule_based_call: result === 'invalid' ? 'inconclusive' : result,
    model: { name: 'MobileNetV3-Small', version: 'prototype', input: '224×224 RGB' },
    pipeline: {
      image_quality: { passed: result !== 'invalid', score: result === 'invalid' ? 0.58 : 0.94 },
      calibration: { passed: true, method: 'reference-card normalization' },
      roi: { detected: true, score: 0.92 },
      rule_engine: { call: result === 'invalid' ? 'inconclusive' : result, delta_e: Number((6 + Math.random() * 12).toFixed(2)) },
      ml: { label: result === 'invalid' ? 'invalid' : result, confidence },
    },
    evidence: {
      image_sha256: hashLike(file?.name || 'demo-image'),
      payload_sha256: hashLike(`${file?.name || 'demo-image'}:${result}`),
      integrity: 'verified',
    },
    demo_only: true,
  }
}

export async function analyzeImage(file) {
  if (DEMO_MODE) {
    await sleep(1450)
    return demoPrediction(file)
  }

  const body = new FormData()
  body.append('image', file)
  const response = await fetch(`${API_URL}/analyze`, { method: 'POST', body })
  if (!response.ok) throw new Error(`Analysis failed (${response.status})`)
  return response.json()
}

export async function getCases() {
  if (DEMO_MODE) {
    await sleep(250)
    return demoCases
  }
  const response = await fetch(`${API_URL}/cases`)
  if (!response.ok) throw new Error('Unable to load cases')
  return response.json()
}
