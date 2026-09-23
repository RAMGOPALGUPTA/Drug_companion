const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8003/api/v1'
const DEMO_MODE = String(import.meta.env.VITE_DEMO_MODE ?? 'true') !== 'false'

function normalizeError(response, fallback) {
  return response.text().then((text) => {
    try {
      const payload = JSON.parse(text)
      return payload.detail || fallback
    } catch {
      return fallback
    }
  })
}

export async function analyzeImage(file) {
  if (DEMO_MODE) {
    throw new Error('Demo mode is disabled for the integrated backend. Set VITE_DEMO_MODE=true to use fixtures.')
  }

  const body = new FormData()
  body.append('image', file)
  const response = await fetch(`${API_URL}/analyze`, { method: 'POST', body })
  if (!response.ok) throw new Error(await normalizeError(response, `Analysis failed (${response.status})`))
  return response.json()
}

export async function getCases() {
  const response = await fetch(`${API_URL}/cases`)
  if (!response.ok) throw new Error(await normalizeError(response, 'Unable to load cases'))
  return response.json()
}

export async function getCase(caseId) {
  const response = await fetch(`${API_URL}/cases/${caseId}`)
  if (!response.ok) throw new Error(await normalizeError(response, 'Unable to load case'))
  return response.json()
}

export async function getCaseAnalysis(caseId) {
  const response = await fetch(`${API_URL}/cases/${caseId}/analysis`)
  if (!response.ok) throw new Error(await normalizeError(response, 'Unable to load analysis'))
  return response.json()
}

export async function getCaseEvidence(caseId) {
  const response = await fetch(`${API_URL}/cases/${caseId}/evidence`)
  if (!response.ok) throw new Error(await normalizeError(response, 'Unable to load evidence'))
  return response.json()
}

export async function getCasesSummary() {
  const response = await fetch(`${API_URL}/cases/summary`)
  if (!response.ok) throw new Error(await normalizeError(response, 'Unable to load case summary'))
  return response.json()
}

export async function getModelInfo() {
  const response = await fetch(`${API_URL}/model`)
  if (!response.ok) throw new Error(await normalizeError(response, 'Unable to load model information'))
  return response.json()
}
