# SIH26231 — Field Evidence Console

A distinctive React/Vite website for the Digital Companion for Field Drug Testing prototype.

## Run

```bash
npm install
npm run dev
```

Open http://localhost:5173

## Backend connection

Create `.env.local` from `.env.example` and set:

```bash
VITE_API_URL=http://localhost:8000/api/v1
VITE_DEMO_MODE=false
```

The New Test screen sends images to:

```text
POST /api/v1/analyze
Content-Type: multipart/form-data
image=<file>
```

Expected response shape is documented in `src/services/api.js`.

## Model contract

The supplied model package declares:

- MobileNetV3-Small
- input: 224 × 224 × 3 RGB
- normalization: 0–1
- classes: negative, positive, invalid

The website does not run the TFLite model in-browser. It calls the backend inference endpoint so the complete Python preprocessing/inference pipeline can stay together.
