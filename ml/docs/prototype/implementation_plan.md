# Revised Implementation Plan: Automated strip_assay Pipeline

**Project:** `strip_assay`  
**Goal:** Automate the complete Data → Training → Validation → TFLite → Inference pipeline for smartphone-based interpretation of colorimetric field-test strips, adhering to strict anti-fabrication rules, evidence integrity, and scientific dataset rigor.  
**Plan Status:** REVISED (Pre-Implementation Review)

---

## 1. Blocking Inputs

The following external dependencies are **strictly required** before any target-specific model training, chemical validation, or production deployment can occur:

1. **Exact Target Test Kit:** The specific physical manufacturer kit (e.g. brand, product line, cassette/strip model).
2. **Exact Test/Analyte Classes:** Documented chemical reagent classes targeted by the kit (e.g. specific alkaloids, synthetic opioids, stimulants).
3. **Kit-Specific Positive/Negative Reference Colors:** Certified spectrophotometric or calibrated CIELAB/sRGB colorimetric endpoints for positive, negative, and blank/control pad reactions under standardized illuminants (D65).
4. **Ground-Truth Labelled Target Images:** Authentic smartphone captures of actual test strips exposed to verified reference substances and adulterants/controls, confirmed by laboratory instruments (e.g., GC-MS).
5. **Authorized Source/Lab for Real Target Data:** Official access to data originating from accredited forensic laboratories, research institutions, or manufacturer quality assurance panels.
6. **Manufacturer-Specific ROI & Reference-Card Geometry:** Physical dimensions, pad spacing, fiducial markers, and certified color coordinates for the physical color calibration card.

### Distinction: Automatable vs. Non-Automatable Tasks

| Category | Tasks Included |
|---|---|
| **Fully Automatable** | • Discovery of public datasets and licensing audit<br>• Permitted public dataset downloading and SHA-256 verification<br>• Ingestion, archive extraction, file normalization, and deduplication<br>• Image quality gate (blur, exposure, clipping checks)<br>• 4-way grouped data splitting by physical sample ID<br>• Canonical preprocessing pipeline (dynamic resolution, color spaces)<br>• MobileNetV3-Small transfer learning & checkpointing<br>• CIEDE2000 Delta-E colorimetric distance calculation<br>• Evaluation metrics, confusion matrices, and per-class reports<br>• TFLite export (FP32, FP16, INT8 with representative calibration)<br>• INT8 acceptance criteria benchmarking against FP32<br>• Decision arbitration and tamper-evident SHA-256 evidence hashing<br>• Experiment tracking and automated readiness reporting |
| **Not Automatable Without External Input** | • Obtaining physical controlled-substance samples (DEA Schedule I–IV)<br>• Wet-chemistry field-test execution and laboratory GC-MS verification<br>• Authoritative certification of chemical reference endpoints<br>• Selection of the specific physical commercial kit<br>• Legal accreditation or forensic admissibility certification |

---

## 2. Target Kit Configuration Architecture

To uphold scientific and forensic validity, the system **must never invent chemistry-specific reference values**. 

- Any generic or fictitious kit configurations (such as `generic_tri_analyte_v1.json`) are **completely removed**.
- We establish an explicit JSON schema and an unconfigured template:
  - `config/kits/schema.json`
  - `config/kits/TEMPLATE_DO_NOT_USE.json`
- The template defines placeholders for:
  - `kit_id`, `manufacturer`, `test_type`, `analyte_list`
  - `positive_reference` (CIELAB), `negative_reference` (CIELAB)
  - `roi_geometry` (pad count, orientation, relative spacing, aspect ratios)
  - `reference_card` (patch count, certified sRGB patches, allowable residual MAE)
  - `deltae_thresholds` (`confident_match`, `confident_nonmatch`)
- We add `docs/KIT_CONFIGURATION_REQUIRED.md` which mandates that all kit parameters originate from an authoritative source (manufacturer specification, certified analytical laboratory, or empirical spectrophotometer measurements).

---

## 3. Dual Model States: Bootstrap vs. Target-Validated

The system strictly bifurcates models into two distinct states to prevent unvalidated models from ever being deployed to field operations:

```
models/
├── bootstrap/
│   ├── checkpoints/
│   ├── mobilenetv3_small_float32.tflite
│   ├── mobilenetv3_small_float16.tflite
│   └── mobilenetv3_small_int8.tflite
└── target_validated/
    ├── checkpoints/
    ├── mobilenetv3_small_float32.tflite
    ├── mobilenetv3_small_float16.tflite
    └── mobilenetv3_small_int8.tflite
```

### Definitions & Deployment Rules:
- **Bootstrap Model (`models/bootstrap/`):**
  - Trained on permitted non-target surrogate datasets (e.g. lateral flow immunoassays, urine test strips, open colorimetric benchmarks) or controlled synthetic data.
  - **Purpose:** Validates the end-to-end data pipeline, MobileNetV3 architecture, TFLite conversion, and inference speed.
  - **Restriction:** The pipeline **refuses** to label a bootstrap model as `"production"`, `"forensic"`, or `"target validated"`. Production deployment scripts will abort if pointed to a bootstrap model for target kit inference.
- **Target-Validated Model (`models/target_validated/`):**
  - Fine-tuned and rigorously evaluated using authentic, laboratory-confirmed target kit data.
  - Only models passing the full evaluation battery on unseen physical target samples may be promoted to `PRODUCTION_CANDIDATE`.

---

## 4. Programmatic Dataset Tier Enforcement

Every discovered or ingested dataset is programmatically classified into one of four rigid tiers:

- **Tier A (Target Relevant):** Real smartphone images of the specific target chemical field-test kit with laboratory ground-truth labels. (`target_domain = true`)
- **Tier B (Relevant Colorimetric Methodology):** Authentic smartphone/digital colorimetric test strips (e.g. urinalysis dipsticks, pH strips, lateral flow assays) with verified color reactions. (`target_domain = false`)
- **Tier C (Pretraining & Augmentation):** General color charts (e.g. ColorChecker), laboratory assay images, or controlled synthetic frames used exclusively for pipeline benchmarking and feature pretraining. (`target_domain = false`)
- **Tier D (Unsuitable):** Unlicensed, scraped, uncalibrated, blurry, or irrelevant web images. Automatically quarantined and rejected.

### Programmatic Enforcement:
- Datasets must include metadata attributes: `dataset_tier` (`"A"`, `"B"`, `"C"`, `"D"`) and `target_domain` (`true`/`false`).
- Training scripts dynamically output:
  - `target_specific_training: true/false`
  - `target_specific_test: true/false`
- If Tier A data is absent, the system executes **bootstrap training only**, and every generated report explicitly prints:
  > `"Target-specific model validation is unavailable."`
- The system prevents mixing Tier B/C metrics with target-specific performance.

---

## 5. Minimum Dataset Requirements

Dataset adequacy is tracked across physical and environmental dimensions, **not merely by raw image count**:

- **Physical Tracking Dimensions:**
  - `unique_physical_samples`: Distinct test strips / chemical reactions evaluated.
  - `unique_batches`: Separate manufacturing lots or chemical preparation runs.
  - `images_per_sample`: Multiple captures per physical sample under varying conditions.
  - `unique_devices`: Distinct smartphone models / camera sensors used.
  - `unique_lighting_conditions`: Documented lux levels and color temperatures (e.g. direct sunlight, fluorescent, low light, warm LED).
  - `unique_operators`: Distinct individuals performing the test and capture.

### Configurable Minimum Thresholds for Target Validation:
- Minimum unique physical samples per class: $\ge 50$
- Minimum independent manufacturing batches: $\ge 3$
- Minimum capture devices: $\ge 3$
- Minimum distinct lighting conditions: $\ge 3$

If these criteria are unmet, `reports/data_readiness.json` records `"insufficient_target_data": true`. No data may be fabricated to satisfy these minimums.

---

## 6. Grouped Data Splitting (Preventing Leakage)

Simple random image-level splitting (e.g. 70/15/15) is strictly prohibited because multiple photos of the same physical strip share identical reagent color artifacts and fiber textures, causing catastrophic data leakage.

### 4-Way Grouped Split Strategy:
Data is grouped strictly by `sample_id` (with secondary grouping on `batch_id`, `operator_id`, `device_id` where applicable) into four independent partitions:

1. **TRAIN:** Used exclusively for neural network weight optimization and model fitting.
2. **VALIDATION:** Used for architecture selection, learning rate scheduling, and early stopping.
3. **CALIBRATION:** Holdout partition reserved strictly for post-hoc confidence calibration (e.g. temperature scaling) and CIEDE2000 decision threshold grid search.
4. **TEST:** Completely untouched, physically independent holdout partition evaluated **once** for final reporting.

> [!CAUTION]
> The **TEST** split is strictly quarantined. It must **never** be used for model selection, hyperparameter tuning, temperature scaling, or arbitration threshold adjustments.

---

## 7. Domain-Transfer Training Strategy

Training proceeds through a formal three-stage progression:

```
┌──────────────────────────────────────────────┐
│ Stage 1: Bootstrap Pretraining               │
│ (Permitted Tier B/C Colorimetric Data)       │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Stage 2: Target-Kit Fine-Tuning              │
│ (Authentic Tier A Lab-Confirmed Data)        │
└──────────────────────┬───────────────────────┘
                       │ (Blocked if Tier A Unavailable)
                       ▼
┌──────────────────────────────────────────────┐
│ Stage 3: Unseen Target Holdout Evaluation    │
│ (Physical Test Partition - Grouped by Sample)│
└──────────────────────────────────────────────┘
```

- If Stage 2 data is unavailable, the pipeline stops after Stage 1, exports the resulting weights to `models/bootstrap/`, and labels all outputs as `BOOTSTRAP / NON-TARGET`.

---

## 8. External Generalization & Robustness Battery

To ensure real-world reliability across uncontrolled smartphone environments, evaluation executes a 5-test robustness matrix (where metadata permits):

- **Test A (Grouped Random Test):** Held-out physical samples across familiar environments.
- **Test B (Unseen Physical Batch):** Test strips originating from an unobserved manufacturing lot.
- **Test C (Unseen Smartphone/Device):** Images captured exclusively on camera models absent from training.
- **Test D (Unseen Lighting Condition):** Captures conducted under unobserved illumination spectra/lux.
- **Test E (Unseen Operator):** Tests executed and imaged by independent personnel.

If specific metadata fields are missing in the dataset, the evaluation engine explicitly outputs `NOT AVAILABLE` rather than interpolating or fabricating metrics.

---

## 9. Calibration Holdout & Confidence Policy

### Optional Temperature Scaling:
Raw softmax outputs cannot be treated as true probabilities. Rather than blindly applying temperature scaling:
1. Compute baseline **Expected Calibration Error (ECE)** and reliability diagrams on the `CALIBRATION` split.
2. Evaluate post-hoc scaling (e.g. Platt scaling / Temperature Scaling).
3. **Adoption Criterion:** Retain temperature scaling **only if** ECE improves without degrading Macro F1 or increasing false-negative rate on high-risk classes.
4. Document findings and confidence interpretation thresholds in `docs/CONFIDENCE_POLICY.md`.

---

## 10. INT8 Quantization & Acceptance Criteria

Because reagent pad analysis relies on subtle color differences, INT8 quantization can shift color boundaries or truncate dynamic range.

### Explicit Acceptance Criteria:
The pipeline exports and benchmarks four model variants on identical calibration/test sets:
1. Keras FP32 (Baseline reference)
2. TFLite FP32
3. TFLite FP16
4. TFLite INT8

### Monitored Metrics:
- Macro & Weighted F1 score
- False Negative Rate (FNR) on positive drug classes
- Prediction agreement with FP32 baseline ($\ge 98.5\%$)
- Mean absolute confidence shift ($< 0.03$)
- On-device inference latency

**Failure Action:** If INT8 accuracy or agreement drops below acceptable evidentiary thresholds, the deployment script **rejects INT8 deployment**, outputs:
> `"INT8 deployment rejected due to validation degradation."`
and initiates diagnostic analysis (evaluating representative dataset quality, input/output tensor ranges, or falling back to TFLite FP16).

---

## 11. Representative Dataset for Quantization

Documented in `docs/TFLITE_QUANTIZATION.md`:
- Drawn strictly from the `TRAIN` and `CALIBRATION` partitions (never from `TEST`).
- Stratified sampling across all classes, illuminations, and camera devices.
- Subjected to the exact canonical preprocessing pipeline.
- Stored as a repeatable generator yielding 100–300 representative input tensors.

---

## 12. Dynamic Preprocessing & Formal Model Input Spec

### Removal of Hardcoded 224x224 Assumption:
- Model input dimensions are decoupled from the code and dynamically derived from the model architecture definition or loaded TFLite input tensor shape (`model_input_shape`).
- Preprocessing dynamically resizes to the shape declared by the active model specification.

### Formal Contract (`docs/MODEL_INPUT_SPEC.md`):
Defines the authoritative cross-platform specification for Python and Android Kotlin implementations:
- Input color format: sRGB (channel order explicitly handled: BGR from OpenCV converted to RGB).
- Color range & dtype: Float32 `[0.0, 1.0]` or Quantized Int8 `[-128, 127]` / Uint8 `[0, 255]`.
- Normalization formula: $(x - \text{mean}) / \text{std}$ or linear scaling $[0, 1]$.
- Resize interpolation: Bilinear / Area interpolation with antialiasing.
- Pad crop geometry and alignment relative to reference card fiducials.
- Output tensor shape and class label ordering: `["negative", "positive", "invalid"]`.

---

## 13. Security, Evidence Integrity & Cryptographic Hashing

### Terminology & Integrity Rules:
- **Cryptographic Integrity Verification:** The pipeline utilizes SHA-256 hash chains over input images, preprocessing parameters, intermediate calibration matrices, Delta-E vectors, and ML predictions. This guarantees tamper detection.
- **Digital Signatures:** The term *"Digital Signature"* is strictly avoided unless an asymmetric public/private key cryptographic signing scheme (e.g., Ed25519) is explicitly configured. All documentation and evidence packets will use `"Cryptographic integrity verification"`.
- If an asymmetric signing module is later integrated, it must specify key generation, secure hardware keystore storage, and certificate rotation.

---

## 14. Forensic Integrity & Regulatory Phrasing

- Vague statements like *"compliant with forensic standards"* are eliminated.
- Replaced with:
  > *"Designed with evidence integrity, algorithmic traceability, and forensic-oriented documentation considerations."*
- Explicit disclaimers state that this system is a presumptive screening tool requiring confirmatory laboratory testing (GC-MS / LC-MS) for judicial or legal admissibility.

---

## 15. Dataset & Experiment Provenance

### Dataset Versioning (`reports/dataset_manifest.json`):
Records for every ingested resource:
- Source name, official URL, dataset version/DOI
- Applicable license terms and redistribution rights
- SHA-256 digest of original archive
- Ingestion date, image count, and sample count
- Assigned `dataset_tier` (A/B/C/D) and `target_domain` boolean

### Experiment Tracking (`experiments/`):
Every training and tuning run writes an immutable directory `experiments/EXP-XXX/`:
- `config.json`: All hyperparameters, loss functions, optimizer settings, seeds.
- `dataset_manifest_hash`: Digest linking directly to the input dataset version.
- `git_commit`: Repository source code hash.
- `model_metadata.json`: Architecture, input shape, quantization parameters.
- `metrics.json`: Train, validation, calibration, and test metrics.
- Exported model weights and TFLite files.

---

## 16. Reproducible Execution Environment

- `requirements-lock.txt` pinning exact versions of `tensorflow==2.21.0`, `opencv-python-headless==4.13.0`, `numpy==2.2.4`, `scipy`, `pandas`, `scikit-learn`, `matplotlib`.
- Environment specification documenting Python 3.13 ABI and platform notes.

---

## 17. Scope Prioritization (P0–P3)

To ensure core evidentiary and execution capabilities are never compromised by secondary features, work is divided into four priority levels:

```
┌─────────────────────────────────────────────────────────────────┐
│ P0: MUST WORK (Core Pipeline & Evidentiary Integrity)           │
│ 1. Dataset Ingestion & Validation                              │
│ 2. Grouped Sample-ID Splitting (Train/Val/Cal/Test)             │
│ 3. Canonical Preprocessing Contract                             │
│ 4. MobileNetV3 Training & Checkpointing                         │
│ 5. Comprehensive Model Evaluation & Test Metrics                │
│ 6. TFLite Export (FP32, FP16, INT8)                             │
│ 7. TFLite INT8 Validation & Acceptance Benchmarking             │
│ 8. Inference Integration (Preserve Existing Dual-Path API)      │
│ 9. CIEDE2000 + ML Decision Arbitration                          │
│ 10. SHA-256 Cryptographic Evidence Packet Generation            │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ P1: IMPORTANT (Robustness & Provenance)                         │
│ 1. Confidence Calibration & ECE Analysis                        │
│ 2. Structured Error Analysis (FP/FN/Disagreements)              │
│ 3. External Generalization Testing (Device/Batch/Lighting)      │
│ 4. Immutable Dataset Manifest & Versioning                      │
│ 5. Experiment Tracking System (experiments/EXP-XXX/)            │
│ 6. Data Readiness Determination Engine                          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ P2: NICE TO HAVE (Workflow Automation)                          │
│ 1. Automated Dataset Discovery & License Classifier             │
│ 2. One-Command Pipeline Orchestrator (run_all.py)               │
│ 3. Advanced Visualization & Training Curve Generation           │
│ 4. Automated Collection Template Generator                      │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ P3: FUTURE (Field Enhancements)                                 │
│ 1. Web/Mobile Verification Dashboard                            │
│ 2. QR-Code Encoded Evidence Verification                        │
│ 3. Asymmetric Digital Signature (Hardware Keystore)             │
│ 4. Multi-Analyte Commercial Kit Expansions                     │
└─────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Priority Rule:** P2 and P3 tasks must **never** block or delay the completion, verification, and hardening of P0 tasks.

---

## 18. Gated Automation Strategy & Readiness States

The pipeline abandons blind linear execution in favor of a gated decision tree:

```
               [DISCOVERY / INGESTION]
                         │
                         ▼
               [LICENSE & TIER AUDIT]
                         │
                         ▼
                 [DATA VALIDATION]
                         │
                         ▼
             [CHECK DATA READINESS STATE]
                         │
       ┌─────────────────┴─────────────────┐
       ▼                                   ▼
 [TARGET DATA AVAILABLE]         [NO TARGET DATA]
       │                                   │
       ▼                                   ▼
{TARGET TRAINING PIPELINE}       {BOOTSTRAP PIPELINE}
 - Fine-tune on Target            - Train on Tier B/C
 - Evaluate Unseen Holdout        - Smoke-test TFLite
 - If checks pass:                - Label: BOOTSTRAP ONLY
   PRODUCTION_CANDIDATE           - Explicitly Report:
                                    "Target Validation
                                     Unavailable"
```

### 5 Explicit Data Readiness States:
1. `NOT_READY`: No valid training data ingested; pipeline halts.
2. `BOOTSTRAP_READY`: Permitted Tier B/C surrogate or synthetic data available; allows pipeline verification only.
3. `TARGET_TRAINING_READY`: Authentic Tier A target data meets minimum sample/batch/device criteria for model training.
4. `TARGET_VALIDATION_READY`: Physical target holdouts available for independent validation, calibration, and testing.
5. `PRODUCTION_CANDIDATE`: Target model has cleared all accuracy, generalization, INT8 degradation, and arbitration gates.

> [!CAUTION]
> The system **refuses** to transition directly from `BOOTSTRAP_READY` to `PRODUCTION_CANDIDATE`.

---

## 19. Final Report Structure (`FINAL_PIPELINE_REPORT.md`)

The final report presents four segregated, unmixed performance sections:
- **Section A: Bootstrap Performance:** Performance on surrogate/synthetic colorimetric data.
- **Section B: Target-Specific Performance:** Authenticated metrics on real target kits (or explicit declaration that target validation is unavailable).
- **Section C: External Generalization Performance:** Breakdown across unseen devices, batches, and illuminants.
- **Section D: TFLite Deployment Performance:** FP32 vs. FP16 vs. INT8 accuracy, agreement rate, degradation status, and inference latency.

---

## 20. Phased Implementation Roadmap

Work proceeds sequentially across 13 controlled phases:

- **Phase 0: Audit & Plan Correction** (Current phase: establish audit, plan changelog, and corrected plan).
- **Phase 1: Dataset Discovery & Source Verification** (Public research repo audit, licensing verification).
- **Phase 2: Dataset Ingestion & Validation** (Raw/interim/processed structure, deduplication, quarantine, grouped split).
- **Phase 3: Data Readiness Determination** (Assess data adequacy, generate `reports/data_readiness.json`).
- **Phase 4: Bootstrap Training Pipeline** (Pretraining on permitted non-target data, verify MobileNetV3 convergence).
- **Phase 5: Target Data Integration** (Configure kit schema and assess external acquisition requirements).
- **Phase 6: Target-Specific Training** (Fine-tuning on target kits if available; otherwise maintain bootstrap gate).
- **Phase 7: Evaluation & Error Analysis** (Evaluate on untouched holdout; analyze false positives/negatives).
- **Phase 8: Confidence Calibration & Arbitration** (Optional temperature scaling, CIEDE2000 + ML arbitration).
- **Phase 9: TFLite Export & Quantization Validation** (Export FP32/FP16/INT8, evaluate degradation).
- **Phase 10: Inference Integration** (Wire model into existing inference engine without breaking legacy API).
- **Phase 11: Evidence Integrity** (Harden SHA-256 chaining, verify cross-platform UTF-8 consistency).
- **Phase 12: Final Reporting** (Compile `docs/FINAL_PIPELINE_REPORT.md` and `docs/MODEL_CARD.md`).

---

## 21. Plan Verification Checklist (15 Critical Criteria)

| # | Verification Criterion | How Revised Plan Resolves It |
|---|---|---|
| 1 | **What exact data is required?** | Documented in Section 1: Exact target kit, certified positive/negative Lab reference colors, verified GC-MS ground truth labels, and multi-condition smartphone photos. |
| 2 | **What can be automated?** | Documented in Section 1 table: Discovery, ingestion, validation, splitting, preprocessing, training, evaluation, TFLite conversion, INT8 benchmarking, arbitration, hashing, reporting. |
| 3 | **What requires external human/lab input?** | Documented in Section 1 table: Controlled substance acquisition, chemical testing, reference color certification, kit selection, forensic accreditation. |
| 4 | **How is target data distinguished from bootstrap data?** | Programmatic metadata tags (`dataset_tier` A vs B/C, `target_domain: bool`) and separate storage (`models/bootstrap/` vs `models/target_validated/`). |
| 5 | **How is leakage prevented?** | Grouped 4-way splitting strictly by physical `sample_id` (all frames of one sample reside in a single split). |
| 6 | **How are train/val/cal/test separated?** | Section 6: TRAIN (fitting), VALIDATION (model selection), CALIBRATION (temperature scaling/thresholds), TEST (untouched evaluation). |
| 7 | **How is external generalization tested?** | Section 8: 5-test matrix evaluating unseen batches, devices, lighting conditions, and operators. |
| 8 | **How is confidence calibrated?** | Section 9: ECE measured on CALIBRATION split; temperature scaling applied only if calibration improves without degrading accuracy. |
| 9 | **How is INT8 quality validated?** | Section 10: Quantitative benchmark comparing Keras FP32, TFLite FP32, FP16, INT8 on accuracy, FNR, agreement ($>98.5\%$), and confidence shift. Rejected if degraded. |
| 10 | **How is preprocessing kept consistent?** | Section 12: Formal contract in `docs/MODEL_INPUT_SPEC.md` specifying dynamic shape, color spaces, normalization, and identical transforms across train and inference. |
| 11 | **How are datasets versioned?** | Section 15: `reports/dataset_manifest.json` tracking source, DOI, license, archive SHA-256, and tier. |
| 12 | **How are experiments versioned?** | Section 15: `experiments/EXP-XXX/` storing hyperparameters, commit hash, dataset manifest digest, and model metadata. |
| 13 | **How is SHA-256 distinguished from digital signatures?** | Section 13: Terminology strictly enforced as "Cryptographic integrity verification"; "Digital signature" reserved only for asymmetric public-key cryptography. |
| 14 | **What prevents a bootstrap model from being deployed as a target model?** | Section 3: Distinct directory paths, refusal of pipeline to tag bootstrap as production, and execution blocks in deployment scripts. |
| 15 | **What is P0 versus optional work?** | Section 17: Explicit P0 (Must Work), P1 (Important), P2 (Nice to Have), P3 (Future) hierarchy. P2/P3 prohibited from blocking P0. |

---

## 22. Verification & Testing Strategy

1. **Automated Unit & Pipeline Tests:**
   - Execute test suite checking Quality Gate, 3x3 Calibration, ROI extraction, CIEDE2000 formulas, and SHA-256 evidence chain verification.
2. **Gated Workflow Validation:**
   - Verify that data readiness state transitions properly from `NOT_READY` to `BOOTSTRAP_READY` without skipping directly to `PRODUCTION_CANDIDATE`.
3. **Model & Quantization Benchmarks:**
   - Verify generation and numerical consistency of FP32, FP16, and INT8 models using representative calibration datasets.
4. **Console & Cross-Platform Integrity:**
   - Verify that all outputs handle UTF-8 encoding safely without crashing under Windows cp1252.
