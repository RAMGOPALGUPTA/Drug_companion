# SIH — Digital Companion for Field Drug Testing

An offline-first companion for documenting a presumptive field test, synchronizing an immutable digest-backed record, and reviewing synced records in an operations dashboard.

> This is an interpretation aid for a presumptive colorimetric field test. It is not laboratory confirmation or definitive drug identification.

## What is built

- Expo/React Native capture workflow with camera capture, optional location, a persistent local SQLite outbox and replay-safe API sync.
- FastAPI service with input validation, CORS configuration, case summaries, result filtering and SHA-256-backed record verification.
- PostgreSQL schema for operators, cases, evidence digests and audit events.
- React operations dashboard with live totals, result filtering, refresh/error states and the required safety notice.
- TensorFlow training/export scripts that validate labelled data and save real validation artifacts only after training.

The mobile app deliberately stores new captures as `inconclusive` with a `pending-labelled-training-data` model version. It must not show an AI result before a real model has been trained, evaluated and explicitly approved.

## Run the API and dashboard

Install Docker Desktop, then from the repository root run:

```bash
docker compose -f infra/docker-compose.yml up --build
```

- API documentation: `http://localhost:8000/docs`
- Operations dashboard: `http://localhost:5173`
- Health check: `http://localhost:8000/health`

The compose stack provisions a local development database with the `demo-operator` account. Replace these development credentials, introduce authenticated operators and set production CORS origins before deployment.

## Run the mobile app

The mobile source is an Expo Android-first app in `mobile/`.

```bash
cd mobile
npm install
npx expo start
```

The app uses `http://10.0.2.2:8000` by default, which addresses a host machine from the Android emulator. Set `EXPO_PUBLIC_API_BASE_URL` to a reachable API address for a physical device, and set `EXPO_PUBLIC_API_OPERATOR_ID` to a provisioned API operator (the local development database uses `demo-operator`). Camera and foreground-location permissions are declared in `mobile/app.json`.

## Train only with real labelled data

Place approved, labelled images outside source control using the following shape:

```text
ml/dataset/raw/
  negative/
  positive/
  inconclusive/
```

At least five readable images per class are needed to run the script; that is only a technical minimum, not a release-quality dataset. Keep an independent, reviewed holdout set and record dataset provenance before considering deployment.

```bash
cd ml
python -m pip install -r requirements.txt
python train.py --data dataset/raw --output artifacts
python export_tflite.py --model artifacts/model.keras --output ../mobile/assets/model.tflite
```

Training writes `model.keras`, labels, metrics, a confusion matrix and a per-class report to `ml/artifacts/`. No training data, model, metrics or claimed accuracy is committed to this repository. Integrating a released TensorFlow Lite model into the mobile prediction flow is the next controlled step after validation.

## Repository map

| Path | Purpose |
| --- | --- |
| `mobile/` | Expo field-capture app and persistent local outbox |
| `backend/` | Record synchronization and digest verification API |
| `dashboard/` | Operations UI |
| `infra/` | Local PostgreSQL and compose setup |
| `ml/` | Dataset validation, training and TFLite export |
