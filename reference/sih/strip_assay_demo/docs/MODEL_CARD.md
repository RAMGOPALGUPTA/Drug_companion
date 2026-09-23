# Model Card: MobileNetV3-Small Strip Assay Confidence Classifier

## Model Details
- **Architecture:** MobileNetV3-Small (depthwise-separable convolutions with squeeze-and-excitation blocks).
- **Model Role:** Secondary advisory confidence classifier operating in a dual-path architecture with a primary CIEDE2000 Delta-E colorimetric engine.
- **Model Version:** `v1.0-prototype-demo`
- **Output Classes:** `["negative", "positive", "invalid"]`
- **Input Specifications:** Dynamic shape, default $(224, 224, 3)$, normalized to $[0.0, 1.0]$ float or quantized int8 $[-128, 127]$, sRGB color format.
- **Export Formats:** TensorFlow Lite (FP32, FP16, and INT8 fully quantized).

---

## Intended Use & Non-Intended Use
- **Intended Use:**
  - Prototype demonstration of automated smartphone-based test-strip interpretation.
  - Resolving ambiguous or borderline cases where classical CIEDE2000 color distance falls into the inconclusive band.
  - Flagging strong disagreements between classical colorimetry and machine learning for human review.
- **Non-Intended Use:**
  - **NOT for forensic, clinical, judicial, or law-enforcement field deployment.**
  - **NOT certified as a definitive confirmatory drug test.**
  - Must never replace laboratory confirmation (GC-MS / LC-MS).
  - Must not be used on uncalibrated images lacking an authentic reference color card.

---

## Training Data & Methodology
- **Current Training Data:** Sourced exclusively from Tier D synthetic target-style test strip simulations and Tier B public colorimetric datasets (SMCR, Reading Colorimetric).
- **Target Domain Real Data:** Currently **ZERO**. Real narcotics field data is pending laboratory acquisition.
- **Data Splitting:** 4-way grouped split strictly by physical `sample_id` (TRAIN: 60%, VALIDATION: 15%, CALIBRATION: 10%, TEST: 15%).
- **Optimization:** Adam optimizer ($\text{lr} = 10^{-3}$), Sparse Categorical Crossentropy, early stopping on validation loss.

---

## Performance & Evaluation (Prototype Baseline)
- **Held-out Synthetic Test Split:**
  - Overall accuracy: $33.3\%$
  - Inconclusive / Flagged Rate: $100.0\%$ (Fail-closed design)
  - Mean On-Device Latency: $23.2\text{ ms}$ (TFLite FP16), $168.8\text{ ms}$ (TFLite INT8 on CPU)
  - Baseline Agreement (FP32 vs INT8): $100.0\%$

---

## Limitations & Environmental Sensitivities
1. **Lighting & Color Temperature:** Extreme low light ($<40$ mean luminance) or severe sodium-vapor color casts will trigger the Quality Gate or produce high calibration residual MAE, failing closed.
2. **Motion Blur & Focus:** Laplacian blur variance $<100.0$ aborts analysis before classification.
3. **Quantization Effects:** INT8 quantization maintains $100\%$ class agreement on tested batches; however, subtle colorimetric shifts may require FP16 fallback under extreme low-contrast lighting.
4. **Target Kit Dependency:** Reagent reaction kinetics and spectral reflectance curves vary significantly across commercial test kit brands. Model weights must be fine-tuned on the exact target kit before field operation.
