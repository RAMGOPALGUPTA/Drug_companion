# Colorimetric Assay Analysis System

Explainable colorimetric assay analysis for narcotics field test strips.
Dual-path architecture: a primary CIEDE2000 Delta-E rule-based engine,
with a secondary MobileNetV3-Small TFLite ML confidence layer used only
to arbitrate ambiguous cases — kept secondary so every call is traceable
to a documented formula and reference value for evidentiary purposes.

## Prototype Data Limitation

> [!IMPORTANT]
> The current prototype uses publicly available colorimetric/lateral-flow datasets and synthetic target-style data because an authorized target-specific field-test dataset was not available during prototype development.
> 
> Therefore the current results demonstrate the software pipeline and deployment architecture, not validated narcotics detection performance.
> 
> Target-kit validation requires appropriately authorized, ground-truthed laboratory/field data.

## Pipeline stages (see `demo_run.py` or `scripts/run_demo.py`)

1. **Quality gate** (`core/quality_gate.py`) — blur (Laplacian variance)
   and exposure (mean luminance, clipped-pixel fraction) checks. Fails
   closed: a bad image aborts with a documented reason rather than
   producing an unreliable call.
2. **Calibration** (`core/calibration.py`) — detects a printed reference
   color card, samples known patches, and fits a 3x3 least-squares color
   correction matrix (observed sRGB → certified sRGB) to remove ambient
   lighting color casts.
3. **ROI extraction** (`core/roi_extraction.py`) — locates the strip and
   slices it into per-analyte reagent pad crops.
4. **Delta-E classification** (`core/deltae_engine.py`) — converts
   calibrated sRGB → CIELAB → CIEDE2000 distance to configured
   positive/negative reference endpoints per analyte. Confident-match /
   confident-nonmatch bands are configurable; the middle band is
   `"inconclusive"`.
5. **ML confidence layer** (`core/ml_confidence.py`) — int8-quantized
   MobileNetV3-Small via TFLite. Resolves `"inconclusive"` Delta-E calls
   when its confidence clears a threshold; flags (never silently
   overrides) strong disagreement with a confident Delta-E call.
6. **Evidence packet** (`evidence/evidence_packet.py`) — JSON record with
   every stage's output plus a SHA-256 hash chain over the stages, the
   final verdicts, and the source image, so any post-hoc edit is
   detectable via `verify_packet()`.

Every run is also appended to `logs/baseline_runs.csv` /
`logs/baseline_runs.jsonl` (`core/baseline_logger.py`) for experiment
tracking across threshold-tuning iterations.

## Quick start

```bash
pip install -r requirements.txt

# Run on a real photo:
python demo_run.py --image path/to/photo.jpg

# Or generate a synthetic smoke-test image first:
python demo_run.py --image sample_data/example_strip.jpg --synthetic
```

Evidence packets land in `evidence_packets/`. To verify a packet hasn't
been tampered with:

```python
from evidence.evidence_packet import verify_packet
print(verify_packet("evidence_packets/<id>.json"))
```

## Phase 12 — tuning thresholds for your kit

1. Collect (or synthesize) a labeled image set:
   ```bash
   python -c "from sample_data.synthetic_generator import generate_dataset; generate_dataset('sample_data/tuning_set', n_samples=200)"
   ```
   For real data, build a `manifest.json` in the same shape
   (`[{"file": "...", "positive_analytes": ["opioid", ...]}, ...]`).

2. Update `core/config.py`:
   - `CalibrationConfig.reference_patches` → your card's certified sRGB values.
   - `DeltaEConfig.analyte_reference_lab` → your kit's positive/negative
     reagent-pad Lab endpoints (measure directly under controlled lighting,
     convert with `core/deltae_engine.rgb_to_lab`).

3. Grid-search the Delta-E thresholds against your labeled set:
   ```bash
   python tune_thresholds.py --data-dir sample_data/tuning_set --optimize-for false_negative_rate
   ```
   This reports accuracy / false-positive / false-negative / inconclusive
   rate per threshold pair. For evidentiary use, minimizing false
   negatives (missed positives) is typically the priority — pick the pair
   that meets your kit's risk tolerance and update `DeltaEConfig` accordingly.

4. Train/export the MobileNetV3-Small ML confidence model separately
   (not included here — this repo expects a trained
   `models/mobilenetv3_small_int8.tflite`) using the same synthetic
   generator's `generate_dataset()` with heavy augmentation
   (`augment_frame`: blur, noise, JPEG compression, gamma) to simulate
   field conditions, then tune `MLConfidenceConfig.min_confidence` and
   `max_disagreement_margin` similarly.

## Project layout

```
core/
  config.py            - all tunable thresholds and reference values
  quality_gate.py       - blur/exposure checks
  calibration.py         - reference-card detection + 3x3 matrix fit
  roi_extraction.py      - strip localization + pad cropping
  deltae_engine.py       - sRGB->Lab, CIEDE2000, classification
  ml_confidence.py       - TFLite MobileNetV3-Small wrapper + resolution logic
  baseline_logger.py     - CSV/JSON experiment logging
evidence/
  evidence_packet.py     - SHA-256 chained tamper-evident packets
sample_data/
  synthetic_generator.py - synthetic frame + augmented dataset generation
demo_run.py               - end-to-end orchestration script
tune_thresholds.py         - Phase 12 threshold grid search
requirements.txt
```

## Android port notes

This Python tree is the reference implementation / desktop verification
harness. For the Flutter/Kotlin Android target:
- `core/quality_gate.py`, `core/calibration.py`, `core/roi_extraction.py`,
  `core/deltae_engine.py` are pure numeric logic with no Python-specific
  dependencies beyond OpenCV/NumPy — port directly to Kotlin using
  `android.graphics`/OpenCV4Android equivalents, keeping the same formulas
  (especially the CIEDE2000 implementation — copy it verbatim to avoid
  divergent results between platforms).
- `core/ml_confidence.py` maps to the Android TFLite Interpreter API
  (`org.tensorflow.lite.Interpreter`), same int8 quantize/dequantize logic.
- `evidence/evidence_packet.py`'s hashing scheme is platform-agnostic JSON
  + SHA-256 — reproduce the exact canonical-JSON serialization
  (sorted keys, no extra whitespace) on Android or hashes won't match
  between platforms if packets are ever cross-verified.
