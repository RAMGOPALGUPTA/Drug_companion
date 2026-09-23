# Drug Companion API

Backend runs on port **8003** for local development.

Base URL: `http://localhost:8003`

## Health

`GET /health`

Returns the API health status.

## Model

`GET /api/v1/model`

Returns the bundled MobileNetV3-Small INT8 artifact metadata, SHA-256, runtime availability, labels, and validation status.

## Analyze

`POST /api/v1/analyze`

Multipart upload field: `image`.

Pipeline:

1. Image decode and quality gate.
2. Reference-card calibration.
3. Strip/pad ROI extraction.
4. CIEDE2000 / Delta-E rule-based classification.
5. MobileNetV3-Small INT8 TFLite inference through LiteRT.
6. Arbitration between rule-based and ML signals.
7. Tamper-evident evidence packet generation.
8. Case creation.

Maximum upload size: 12 MB.

## Cases

- `GET /api/v1/cases`
- `GET /api/v1/cases/summary`
- `GET /api/v1/cases/{case_id}`
- `GET /api/v1/cases/{case_id}/analysis`
- `GET /api/v1/cases/{case_id}/evidence`

The current bootstrap model remains explicitly marked as **not target-validated**. Its inference output must not be represented as forensic validation or production approval.

## Local setup

From `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8003
```

Frontend:

```env
VITE_API_URL=http://localhost:8003/api/v1
VITE_DEMO_MODE=false
```

PostgreSQL development database:

```powershell
cd ..\infra
docker compose up -d
```
