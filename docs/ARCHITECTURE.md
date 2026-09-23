# Drug Companion Architecture

backend: canonical FastAPI runtime
frontend: web application
mobile: field application
dashboard: operational dashboard
ml: training and evaluation
infra: PostgreSQL and local orchestration
docs: contracts and architecture
reference/sih: complete original Sih snapshot for traceability only

Runtime:
Mobile/Web -> FastAPI -> Analysis Service -> Inference Pipeline -> PostgreSQL + Evidence

Inference:
image -> quality gate -> calibration -> ROI -> Delta-E -> MobileNetV3 TFLite -> confidence -> arbitration -> evidence

Classification:
Case = positive | negative | inconclusive
ML = positive | negative | invalid
Final = positive | negative | inconclusive

The migrated prototype model is not target-validated.
