# Target, forensic, and production validation

This directory contains the validation contract for Drug Companion. It deliberately separates software verification from scientific validation.

The bundled model is a synthetic/bootstrap artifact. It must not be promoted to target-validated or production-approved merely because the evaluation code runs.

## Required evidence

A target-validation run must use a locked, independently curated dataset of real target-kit images with a documented reference result for every sample. The reference result must come from an appropriate validated reference method or qualified laboratory process. Synthetic demo images can be used for software tests, but they cannot satisfy the real-world gate.

The dataset should be split before model fitting into independent train/validation/test sets. The test set must remain untouched until the final model is frozen. Where applicable, split by specimen, batch/lot, collection site, camera/device, and capture session to prevent leakage.

Each sample should have provenance fields for sample_id, image identifier, reference result, kit/lot/batch, capture device, site, capture session, collection date/time, reference method and report identifier, operator identifier or blinded operator code, and quality exclusions/reason.

## Performance study

The evaluation harness reports confusion matrix, accuracy on decided samples, coverage, inconclusive or invalid rate, sensitivity, specificity, PPV, NPV, F1, deterministic bootstrap confidence intervals, and per-site/device/batch breakdowns.

Acceptance thresholds are configurable. They are project or laboratory acceptance criteria, not universal regulatory thresholds.

## Forensic validation

Forensic deployment requires more than a high image-classification score. The validation plan must document intended use, reference materials, selectivity, matrix/interference effects, repeatability/reproducibility, robustness, limitations, quality controls, analyst competency, and the relationship between screening and confirmatory analytical methods.

The project therefore keeps forensic validation status separate from target validation status.

## Clinical validation

Clinical validation is only applicable if the intended use becomes a clinical or medical decision function. A field screening tool for seized-material analysis is not automatically a clinical device. If intended use changes to patient diagnosis or clinical decision support, a separate clinical protocol, clinical reference standard, study population, and regulatory assessment are required.

## Production gate

A model can be labelled PRODUCTION_CANDIDATE only when all required evidence is present: frozen target model artifact and SHA-256; locked independent test set; completed target evaluation report; approved acceptance criteria; applicable forensic or clinical validation; robustness and failure-mode testing; model card and limitations; reproducible training/evaluation metadata; and production configuration with demo/fallback behaviour disabled.

Until these conditions are met, the runtime must continue to identify the model as bootstrap or target-candidate rather than production-approved.
