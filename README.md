# Drug Companion

Digital field-testing companion for image-based strip screening, evidence capture, case management, and validation workflows.

## Generated demo dataset

A repository copy of the uploaded synthetic demo fixtures is available under `generated_strip_demo_v1/`. It contains six 1000x800 RGB JPEGs:

- positive_style
- negative_style
- inconclusive_style
- poor_lighting
- blurred
- perspective_distorted

The dataset is explicitly marked synthetic and is intended for prototype demonstrations, pipeline tests, and controlled software experiments. It must not be represented as real-world target validation or forensic validation.

## Live analytics

The Signal Room is backed by persisted case data. It refreshes periodically and derives positive, negative, and inconclusive counts and time-series volume directly from backend cases.

## Case reports

The archive and case dossier provide PDF export through `/api/v1/cases/{case_id}/report`. Reports include case metadata, model status, evidence hashes, and a prototype-use disclaimer.

## Validation

Target evaluation tooling lives under `ml/validation`. Real-world validation requires independently established reference results and a locked target dataset.
