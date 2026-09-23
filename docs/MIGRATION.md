# Sih Migration

The complete original Sih source is preserved under reference/sih.

Runtime reorganization:
- strip assay CV modules -> backend/app/inference
- evidence generation -> backend/app/evidence
- runtime TFLite model + metadata -> backend/models
- training/evaluation/scripts/reports -> ml
- frontend/mobile/dashboard remain first-class applications

backend/legacy contains the previous backend entrypoint as a migration reference only.
