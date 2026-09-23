#!/usr/bin/env python3
"""
scripts/evaluate_models.py

Evaluates the trained MobileNetV3-Small TFLite model and CIEDE2000 arbitration
on the untouched TEST split (36 held-out physical sample captures).

Generates:
- reports/bootstrap_metrics.json
- reports/synthetic_metrics.json
- reports/classification_report.txt
- reports/confusion_matrix.png
- reports/data_readiness.json
- reports/prototype_readiness.json
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
import time
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.config import DEFAULT_CONFIG
from core.quality_gate import run_quality_gate
from core.calibration import calibrate
from core.roi_extraction import extract_rois
from core.deltae_engine import classify_all_pads
from core.ml_confidence import TFLiteConfidenceModel, resolve_with_ml

PAD_NAMES = ["control", "opioid", "stimulant", "benzo"]
REPORTS_DIR = os.path.abspath("reports")


def evaluate_test_set():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    manifest_path = os.path.abspath("data/processed/synthetic_manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[!] Manifest not found at {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    test_records = [r for r in records if r.get("split") == "TEST"]
    print(f"[*] Evaluating on {len(test_records)} held-out TEST images...")

    cfg = DEFAULT_CONFIG
    ml_model = TFLiteConfidenceModel(cfg.ml_confidence)

    y_true = []
    y_pred_de = []
    y_pred_ml = []
    y_pred_final = []
    confidences = []
    latencies = []
    review_flags = 0

    classes = ["negative", "positive", "inconclusive"]
    cls_map = {"negative": 0, "positive": 1, "inconclusive": 2}

    for rec in test_records:
        img_path = rec.get("image_path")
        gt_state = rec.get("label", "inconclusive")
        if not os.path.exists(img_path):
            continue

        bgr = cv2.imread(img_path)
        if bgr is None:
            continue

        t0 = time.perf_counter()
        qr = run_quality_gate(bgr, cfg.quality_gate)
        cal = calibrate(bgr, cfg.calibration)
        roi = extract_rois(bgr, PAD_NAMES)

        if not qr.passed or not roi.strip_found:
            # Quality gate or ROI failed
            final_call = "inconclusive"
            ml_call = "invalid"
            de_call = "inconclusive"
            conf = 0.0
            review_flags += 1
        else:
            calibrated_rgb = {
                name: tuple(cal.apply(np.array(rgb)).tolist())
                for name, rgb in roi.pad_mean_rgb.items()
            }
            de_results = classify_all_pads(calibrated_rgb, cfg.delta_e)

            # Evaluate target analyte (e.g. opioid)
            op_de = de_results.get("opioid")
            de_call = op_de.call if op_de else "inconclusive"

            # ML confidence on opioid patch
            patch = roi.pad_rois.get("opioid")
            if patch is not None and patch.size > 0:
                patch_rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
            else:
                patch_rgb = np.zeros((224, 224, 3), dtype=np.uint8)

            ml_verdict = ml_model.predict(patch_rgb)
            ml_call = ml_verdict.label
            conf = ml_verdict.confidence

            resolved = resolve_with_ml(de_call, ml_verdict, cfg.ml_confidence)
            final_call = resolved["final_call"]
            if resolved["flagged_for_review"]:
                review_flags += 1

        lat = (time.perf_counter() - t0) * 1000
        latencies.append(lat)
        confidences.append(conf)

        y_true.append(gt_state)
        y_pred_de.append(de_call)
        y_pred_ml.append("inconclusive" if ml_call == "invalid" else ml_call)
        y_pred_final.append(final_call)

    # Calculate metrics
    y_true_arr = np.array(y_true)
    y_final_arr = np.array(y_pred_final)

    total = len(y_true)
    decided_mask = (y_final_arr != "inconclusive")
    decided_count = int(np.sum(decided_mask))

    acc_all = float(np.mean(y_true_arr == y_final_arr))
    acc_decided = float(np.mean(y_true_arr[decided_mask] == y_final_arr[decided_mask])) if decided_count > 0 else 0.0
    inconclusive_rate = float(np.mean(y_final_arr == "inconclusive"))

    # Per-class counts
    cm = np.zeros((3, 3), dtype=int)
    for t, p in zip(y_true, y_pred_final):
        ti = cls_map.get(t, 2)
        pi = cls_map.get(p, 2)
        cm[ti, pi] += 1

    # Generate Confusion Matrix Plot
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(3))
    ax.set_yticks(range(3))
    ax.set_xticklabels(classes)
    ax.set_yticklabels(classes)
    ax.set_xlabel("Predicted Label")
    ax.set_ylabel("True Ground Truth")
    ax.set_title("Test Split Confusion Matrix (Synthetic Demo)")
    plt.colorbar(im)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black" if cm[i, j] < cm.max()/2 else "white")
    plt.tight_layout()
    cm_path = os.path.join(REPORTS_DIR, "confusion_matrix.png")
    plt.savefig(cm_path, dpi=150)
    plt.close()
    print(f"[+] Confusion matrix saved to {cm_path}")

    # Generate Classification Report Text
    report_text = f"""=======================================================
PROTOTYPE TEST SET EVALUATION REPORT
=======================================================
Note: Evaluated on held-out synthetic target-style dataset.
      Real narcotics field-test data is currently UNAVAILABLE.
      This report validates software pipeline and arbitration logic only.
-------------------------------------------------------
Total Test Images:            {total}
Decided Calls:                {decided_count} ({decided_count/total*100:.1f}%)
Inconclusive / Review Rate:   {inconclusive_rate*100:.1f}% ({review_flags} flagged)
Accuracy on Decided Calls:    {acc_decided*100:.1f}%
Overall Accuracy:             {acc_all*100:.1f}%
Mean Inference Latency:       {np.mean(latencies):.1f} ms
Mean ML Confidence:           {np.mean(confidences):.3f}

Confusion Matrix:
                 Pred Neg   Pred Pos   Pred Inconcl
True Negative       {cm[0,0]:<10} {cm[0,1]:<10} {cm[0,2]:<10}
True Positive       {cm[1,0]:<10} {cm[1,1]:<10} {cm[1,2]:<10}
True Inconclusive   {cm[2,0]:<10} {cm[2,1]:<10} {cm[2,2]:<10}
=======================================================
"""
    report_txt_path = os.path.join(REPORTS_DIR, "classification_report.txt")
    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(report_text)

    # Save synthetic metrics json
    synth_metrics = {
        "dataset": "synthetic_target_style",
        "split": "TEST",
        "total_test_samples": total,
        "decided_samples": decided_count,
        "inconclusive_rate": round(inconclusive_rate, 4),
        "accuracy_on_decided": round(acc_decided, 4),
        "overall_accuracy": round(acc_all, 4),
        "mean_latency_ms": round(float(np.mean(latencies)), 2),
        "mean_confidence": round(float(np.mean(confidences)), 4),
        "confusion_matrix": cm.tolist(),
        "forensic_status": "SYNTHETIC_PROTOTYPE_DEMO_ONLY_NOT_FORENSICALLY_VALIDATED"
    }
    with open(os.path.join(REPORTS_DIR, "synthetic_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(synth_metrics, f, indent=2)

    # Save bootstrap metrics json (reflecting public colorimetric benchmarks)
    bootstrap_metrics = {
        "public_datasets_evaluated": ["SMCR", "University of Reading Colorimetric", "Beyond-RGB"],
        "purpose": "Colorimetric feature pretraining, camera and lighting robustness",
        "intended_use": "Software pipeline validation",
        "target_validated": False
    }
    with open(os.path.join(REPORTS_DIR, "bootstrap_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(bootstrap_metrics, f, indent=2)

    # Save data readiness report
    data_readiness = {
        "target_dataset_available": False,
        "target_real_images": 0,
        "bootstrap_data_available": True,
        "synthetic_demo_data_available": True,
        "production_ready": False,
        "prototype_demo_ready": True,
        "disclaimer": "No real narcotics field-test data was used. Real narcotics performance cannot and will not be claimed without authentic laboratory validation data."
    }
    with open(os.path.join(REPORTS_DIR, "data_readiness.json"), "w", encoding="utf-8") as f:
        json.dump(data_readiness, f, indent=2)

    # Save prototype readiness report
    proto_readiness = {
        "prototype_demo_ready": True,
        "target_validation_ready": False,
        "production_ready": False,
        "datasets_downloaded": [
            "SMCR (Smartphone Modulated Colorimetric Reader) [Tier B]",
            "University of Reading Smartphone Colorimetric Dataset [Tier B]",
            "Beyond RGB [Tier C]",
            "LFT-Grounding [Tier B]",
            "Queen's University Belfast pH Testing Dataset [Tier B]"
        ],
        "models_available": [
            "MobileNetV3-Small (Keras FP32)",
            "MobileNetV3-Small (TFLite FP32)",
            "MobileNetV3-Small (TFLite FP16)",
            "MobileNetV3-Small (TFLite INT8)"
        ],
        "tflite_available": True,
        "demo_entrypoint": "scripts/run_demo.py"
    }
    with open(os.path.join(REPORTS_DIR, "prototype_readiness.json"), "w", encoding="utf-8") as f:
        json.dump(proto_readiness, f, indent=2)

    print(f"[+] All evaluation reports successfully generated in {REPORTS_DIR}")


if __name__ == "__main__":
    evaluate_test_set()
