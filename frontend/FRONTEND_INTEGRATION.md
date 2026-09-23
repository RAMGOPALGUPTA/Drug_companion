# Frontend ↔ Model Integration Contract

The website intentionally keeps TFLite out of the browser. The frontend uploads the original image to the inference backend.

## Endpoint

`POST /api/v1/analyze`

Request: `multipart/form-data`

```text
image=<field image file>
```

## Response

```json
{
  "case_id": "CASE-1042",
  "result": "positive|negative|invalid",
  "confidence": 0.91,
  "model": {
    "name": "MobileNetV3-Small",
    "version": "prototype",
    "input": "224×224 RGB"
  },
  "pipeline": {
    "image_quality": { "passed": true, "score": 0.94 },
    "calibration": { "passed": true },
    "roi": { "detected": true },
    "rule_engine": { "call": "positive", "delta_e": 8.2 },
    "ml": { "label": "positive", "confidence": 0.91 }
  },
  "evidence": {
    "image_sha256": "...",
    "payload_sha256": "...",
    "integrity": "verified"
  }
}
```

`invalid` is rendered in the website as **INCONCLUSIVE**.

## Demo mode

By default the website uses local demo fixtures. Set `VITE_DEMO_MODE=false` to use the real API.
