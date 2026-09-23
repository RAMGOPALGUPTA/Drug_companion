const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8003/api/v1'

async function parseResponse(response, fallback) {
  if (response.ok) return response.json()
  const text = await response.text()
  try {
    const payload = JSON.parse(text)
    throw new Error(payload.detail || fallback)
  } catch (error) {
    if (error instanceof Error && error.message !== fallback) throw error
    throw new Error(fallback)
  }
}

function requestHeaders(extra = {}) {
  return {
    Accept: 'application/json',
    ...extra,
  }
}

export async function analyzeImage(file, { operatorId = 'demo-operator', location = 'Field capture' } = {}) {
  const body = new FormData()
  body.append('image', file)

  const response = await fetch(`${API_URL}/analyze`, {
    method: 'POST',
    headers: requestHeaders({
      'X-Operator-Id': operatorId,
      'X-Location': location,
    }),
    body,
  })

  return parseResponse(response, `Analysis failed (${response.status})`)
}

export async function getCases() {
  const response = await fetch(`${API_URL}/cases`, {
    headers: requestHeaders(),
  })
  return parseResponse(response, 'Unable to load cases')
}

export async function getCase(caseId) {
  const response = await fetch(`${API_URL}/cases/${encodeURIComponent(caseId)}`, {
    headers: requestHeaders(),
  })
  return parseResponse(response, 'Unable to load case')
}

export async function getCaseAnalysis(caseId) {
  const response = await fetch(
    `${API_URL}/cases/${encodeURIComponent(caseId)}/analysis`,
    { headers: requestHeaders() },
  )
  return parseResponse(response, 'Unable to load analysis')
}

export async function getCaseEvidence(caseId) {
  const response = await fetch(
    `${API_URL}/cases/${encodeURIComponent(caseId)}/evidence`,
    { headers: requestHeaders() },
  )
  return parseResponse(response, 'Unable to load evidence')
}

export async function verifyCaseEvidence(caseId) {
  const response = await fetch(
    `${API_URL}/cases/${encodeURIComponent(caseId)}/evidence/verify`,
    { headers: requestHeaders() },
  )
  return parseResponse(response, 'Unable to verify evidence')
}

export async function getCasesSummary() {
  const response = await fetch(`${API_URL}/cases/summary`, {
    headers: requestHeaders(),
  })
  return parseResponse(response, 'Unable to load case summary')
}

export async function getModelInfo() {
  const response = await fetch(`${API_URL}/model`, {
    headers: requestHeaders(),
  })
  return parseResponse(response, 'Unable to load model information')
}

export async function getStorageStatus() {
  const response = await fetch(`${API_URL}/storage`, {
    headers: requestHeaders(),
  })
  return parseResponse(response, 'Unable to load storage status')
}
