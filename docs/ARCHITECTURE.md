# Drug Companion Architecture

Drug Companion is a field-testing companion for image-based strip analysis.

Runtime:
Mobile/Web -> FastAPI -> Analysis Service -> Inference Pipeline -> PostgreSQL + Evidence

Inference stages:
1. Input validation
2. Image quality gate
3. Reference-card calibration
4. Strip/ROI extraction
5. CIEDE2000 / Delta-E analysis
6. MobileNetV3 TFLite inference
7. ML confidence evaluation
8. Rule/ML arbitration
9. Final classification
10. Evidence packet and SHA-256 integrity
11. Persistence and audit

Classification contract:
- Case: positive | negative | inconclusive
- ML: positive | negative | invalid
- Final: positive | negative | inconclusive

The internal ML value "invalid" is never exposed as a final case classification.

Layer boundaries:
- api: HTTP transport
- schemas: Pydantic contracts
- services: application orchestration
- inference: image analysis and model runtime
- evidence: evidence construction and hashing
- db: PostgreSQL access
- core: configuration and cross-cutting concerns

The legacy Sih prototype is reference material, not the production application boundary.

The supplied prototype model is not target-validated. Runtime registration must record artifact hash, metadata, validation status, and forensic status.
