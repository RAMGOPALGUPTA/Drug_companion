# Drug Companion — final validation and production plan

## Current state

The application is an end-to-end engineering prototype. The bundled MobileNetV3-Small INT8 artifact is executable and integrated, but it is a synthetic/bootstrap model. The validation pipeline is implemented so a target dataset can be evaluated reproducibly without changing the production API.

The project must not silently convert a bootstrap model into a production model. The runtime therefore uses explicit metadata gates.

## Gate A — real-world target validation

Required inputs are real images captured from the intended assay/kit in representative operating conditions; a documented reference result for every sample; immutable image hashes; lot/batch, device, site and session metadata; an independent locked test set; and pre-approved acceptance criteria.

The final report must include sensitivity, specificity, PPV, NPV, coverage, inconclusive rate, confusion matrix, confidence intervals, and breakdowns by site/device/batch.

## Gate B — forensic validation

For a forensic intended use, the validation protocol should be reviewed by the responsible laboratory and aligned with its applicable quality system. The study should address selectivity, matrix/interference effects, repeatability/reproducibility, robustness, reference materials, failure modes, limitations, quality control, analyst competency, and the relationship between screening and confirmatory methods.

SWGDRUG Recommendations 8.2 describe validated analytical methods, representative reference materials, performance characteristics, documentation, and quality assurance as components of forensic drug analysis. The project uses these recommendations as a validation-design reference; they do not constitute accreditation or regulatory approval.

## Gate C — clinical validation

This gate is only relevant if Drug Companion is intended to produce a clinical or medical result. If the project remains focused on seized-material field screening, label the clinical gate not applicable rather than pretending it is completed.

If clinical use is introduced, define intended population, reference standard, study design, endpoints, subgroup analysis, risk controls, and applicable regulatory pathway before collecting validation data.

## Gate D — production candidate

A production candidate requires target validation accepted; applicable forensic or clinical validation accepted; frozen model artifact and SHA-256; model card and intended-use statement; reproducible training/evaluation manifest; failure-mode and robustness testing; database migrations tested; production configuration with no demo fallback; access control/authentication and operational monitoring; incident/audit procedures; and a signed release record.

## What can be completed without laboratory data

Software-side work can be completed now: validation manifest and schema, deterministic evaluation script, acceptance configuration, validation report format, model readiness state machine, model metadata and artifact hashing, CI checks, documentation, and operator-facing disclosure.

What cannot be truthfully generated from software alone is the scientific evidence itself. That requires real target specimens/reference results and qualified validation work.
