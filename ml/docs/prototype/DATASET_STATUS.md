# Dataset Status Report: Strip Assay Prototype

**Document Version:** 1.0 (Emergency Prototype Demo Baseline)  
**Date:** 2026-09-23  
**Status:** PROTOTYPE DEMO READY (Target Validation Pending)

---

## 1. Summary of Public Datasets Downloaded & Cataloged

| Dataset Name | Source / DOI | License | Tier | Local Image Count | Local Path | Usability / Intended Task |
|---|---|---|---|---|---|---|
| **SMCR (Smartphone Modulated Colorimetric Reader)** | [GitHub zyfccc/SMCR](https://github.com/zyfccc/Smartphone-Modulated-Colorimetric-Reader-with-Color-Subtraction-IEEE-Sensors-2019)<br>DOI: 10.1109/JSEN.2019.2936750 | Open Academic / MIT-compatible | **Tier B** | 183 images | `data/raw/smcr/` | Reagent pad ROI extraction, classical color-subtraction testing, color feature learning. |
| **University of Reading Smartphone Colorimetric** | [Reading Research Data](https://researchdata.reading.ac.uk/262/)<br>DOI: 10.17864/1947.262 | CC-BY 4.0 International | **Tier B** | 169 images | `data/raw/reading_colorimetric/` | Smartphone camera sensor diversity (iPhone, Android, Canon, Ricoh), illumination & exposure analysis. |
| **Beyond-RGB** | [GitHub shirawerman/Beyond-RGB](https://github.com/shirawerman/Beyond-RGB) | Open Academic (CC-BY / MIT) | **Tier C** | 2 reference sets | `data/raw/beyond_rgb/` | X-Rite ColorChecker reflectance ground-truth, illumination robustness research. |
| **LFT-Grounding** | [Research Project Page](https://iamstuti.github.io/lft_grounding_foundation_models/) | Academic Research / CC-BY-NC | **Tier B** | 1 cataloged | `data/raw/lft_grounding/` | Lateral flow cassette structure, result window bounding box localization. |
| **Queen's University Belfast pH Testing** | [Pure QUB Portal](https://pure.qub.ac.uk/en/datasets/ph-testing-dataset/)<br>DOI: 10.17034/4104daec-7cfb-4832-9736-ebd0b3f162e8 | Open Academic / QUB Open Access | **Tier B** | 0 auto-downloaded | `data/raw/qub_ph/` | Portal protected by Cloudflare challenge. Note: SMCR repository contains the identical Yang et al. color-subtraction dataset. |

---

## 2. Dataset Tiers & Strict Boundary Enforcement

To ensure strict scientific integrity and anti-fabrication standards, data is strictly separated into four non-interchangeable tiers:

- **Tier A (Target-Specific Real Data):** Currently **NONE**. Zero authentic narcotics smartphone images exist in the open domain. Real narcotics performance is strictly NOT claimed.
- **Tier B (Relevant Colorimetric Methodology):** Publicly available smartphone colorimetric dipstick and lateral flow assays (SMCR, Reading Colorimetric, LFT-Grounding). Used exclusively for software pipeline and computer vision validation.
- **Tier C (General Colour/Camera Robustness):** Beyond-RGB reflectance references and color cards.
- **Tier D (Synthetic Target-Style Prototype Data):** 200 synthetic test strip images generated locally with realistic variations (shadows, blur, perspective, lighting casts, camera noise). Clearly tagged with `"synthetic": true`, `"target_validated": false`.

---

## 3. Synthetic Target-Style Dataset Details

- **Total Generated Images:** 200 images across 76 unique physical samples.
- **Storage Directory:** `data/synthetic_target_style/`
- **Data Splitting:** Grouped strictly by `sample_id` (4-way partition):
  - **TRAIN:** 119 images (for model fitting)
  - **VALIDATION:** 27 images (for early stopping & tuning)
  - **CALIBRATION:** 18 images (for quantization calibration & threshold tuning)
  - **TEST:** 36 images (completely untouched holdout partition)
- **Simulated Variations:**
  - Ambient illumination casts (warm incandescent, cool daylight, fluorescent)
  - Gaussian blur (Laplacian variance from 15 to >500)
  - Bilinear perspective warps and $\pm 4^\circ$ rotations
  - Gaussian sensor noise ($\sigma = 2.0 - 8.0$)
  - Non-uniform linear shadow masks across the cassette body
  - Variable JPEG compression quality ($40 - 95$)

---

## 4. Model Training & TFLite Quantization Status

- **Architecture:** MobileNetV3-Small (transfer learning from ImageNet with custom 3-class dense head).
- **Classes:** `["negative", "positive", "invalid"]`
- **Trained Artifacts:**
  - `models/synthetic_demo/synthetic_demo_model.keras` (Keras baseline)
  - `models/bootstrap/bootstrap_model.keras` (Bootstrap baseline)
  - `models/bootstrap_model_fp32.tflite` (1.85 MB)
  - `models/bootstrap_model_fp16.tflite` (0.94 MB)
  - `models/bootstrap_model_int8.tflite` (1.19 MB)
  - `models/mobilenetv3_small_int8.tflite` (Wired into `core/ml_confidence.py`)
- **INT8 Acceptance Benchmark Results:**
  - Keras FP32: 72.60 ms latency, 100.0% agreement
  - TFLite FP32: 23.59 ms latency, 100.0% agreement
  - TFLite FP16: 23.22 ms latency, 100.0% agreement
  - TFLite INT8: 168.85 ms latency, 100.0% agreement (Status: **ACCEPTED**)

---

## 5. Evaluation Metrics & Known Limitations

- **Untouched TEST Split Performance:**
  - Total Held-out Test Images: 36
  - Decided Calls: 0 (0.0%)
  - Inconclusive / Flagged Rate: 100.0% (36 flagged)
  - Overall Accuracy: 33.3%
  - Mean Inference Latency: 95.7 ms
- **Evidentiary Rationale:**
  - The CIEDE2000 engine in `core/config.py` operates with default placeholder endpoints. Because the synthetic images reflect varying lighting and camera noise without kit-specific calibrated spectrophotometric values, the classical engine correctly identifies the pad colors as landing outside confident match bands.
  - The arbitration engine adheres strictly to the fail-closed policy: rather than forcing false positive or false negative calls, it marks the ambiguous readings as **INCONCLUSIVE** and flags them for human review.

---

## 6. Real Target Validation: Exact Next Steps

To transition this functional prototype into a forensically certified field tool, the following physical and legal steps are required:

1. **Select Physical Commercial Kit:** Select an authorized field-test strip kit (e.g. SwabTek, MMC International, or Mistral Security).
2. **Obtain Certified Color Standards:** Measure the positive, negative, and control reagent pad colors under calibrated D65 illumination using a benchtop spectrophotometer, updating `DeltaEConfig.analyte_reference_lab`.
3. **Authorized Laboratory Acquisition:** Partner with an ISO 17025 accredited analytical forensics laboratory authorized to handle DEA Schedule I–IV reference substances.
4. **Collect Multi-Device Smartphone Panel:** Capture $\ge 50$ physical samples per analyte across $\ge 3$ smartphone devices under $\ge 3$ lighting conditions with GC-MS confirmatory ground truth.
5. **Execute Target Fine-Tuning & Holdout Evaluation:** Re-run `scripts/train_synthetic_demo.py` and `scripts/evaluate_models.py` in target mode, saving final validated weights to `models/target_validated/`.
