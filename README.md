# Drug Companion

Digital field-testing companion for image-based strip analysis.

## Architecture

- backend — FastAPI analysis API, inference pipeline, evidence generation, PostgreSQL persistence
- frontend — field evidence console
- mobile — planned/active client layer
- dashboard — planned/active operational layer
- ml — training, evaluation, and model lifecycle
- infra — PostgreSQL schema and Docker Compose
- docs — architecture and API documentation
- reference/sih — preserved source/reference material

## Backend runtime

The backend currently provides:

- POST /api/v1/analyze for JPEG/PNG/WEBP image analysis
- quality gate, reference calibration, ROI extraction, CIEDE2000 classification
- MobileNetV3-Small INT8 LiteRT inference
- rule/ML arbitration with human-review flags
- tamper-evident SHA-256 evidence packets
- evidence verification at /api/v1/cases/{case_id}/evidence/verify
- PostgreSQL case, analysis-run, evidence, model-registry, and audit persistence
- process-memory fallback when PostgreSQL is unavailable
- /api/v1/cases, case detail, analysis, evidence, summary, model, and storage endpoints
- /health and /ready operational endpoints

## Local backend

From backend:

    .\.venv\Scripts\Activate.ps1
    python -m uvicorn app.main:app --reload --port 8003

For PostgreSQL + backend:

    cd infra
    docker compose up --build

The containerized API is exposed at http://localhost:8003.

## Model status

The bundled MobileNetV3-Small INT8 model is executable through ai_edge_litert, but its metadata marks it as SYNTHETIC_DEMO / BOOTSTRAP with target_validated=false. It must not be represented as target or forensic validation.

## Development verification

Run:

    cd backend
    pytest -q

Then verify:

    Invoke-RestMethod http://localhost:8003/ready
    Invoke-RestMethod http://localhost:8003/api/v1/model
    Invoke-RestMethod http://localhost:8003/api/v1/storage