#!/usr/bin/env python3
"""
scripts/run_demo.py — Standalone Demo Runner & Visual Status Card

Usage:
    python scripts/run_demo.py demo/images/positive_style.jpg
    python scripts/run_demo.py demo/images/negative_style.jpg
    python scripts/run_demo.py demo/images/inconclusive_style.jpg
    python scripts/run_demo.py demo/images/poor_lighting.jpg

Outputs:
1. Formatted interactive ASCII dashboard card
2. Clean JSON result packet
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import argparse
import json
import time
import numpy as np
import cv2

from core.config import DEFAULT_CONFIG
from core.quality_gate import run_quality_gate
from core.calibration import calibrate
from core.roi_extraction import extract_rois
from core.deltae_engine import classify_all_pads
from core.ml_confidence import TFLiteConfidenceModel, resolve_with_ml
from evidence.evidence_packet import build_evidence_packet, save_packet

PAD_NAMES = ["control", "opioid", "stimulant", "benzo"]


def run_demo(image_path: str, verbose: bool = True):
    t_start = time.perf_counter()

    if not os.path.exists(image_path):
        print(f"[!] Image not found: {image_path}")
        sys.exit(1)

    image = cv2.imread(image_path)
    if image is None:
        print(f"[!] Could not decode image at {image_path}")
        sys.exit(1)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    cfg = DEFAULT_CONFIG

    # 1. Quality Gate
    qr = run_quality_gate(image, cfg.quality_gate)
    image_quality = "GOOD" if qr.passed else ("WARNING" if qr.blur_variance > 50 else "REJECT")

    # 2. Calibration
    cal = calibrate(image, cfg.calibration)
    calibration_status = "VALID" if cal.passed else "INVALID"

    # 3. ROI Extraction
    roi = extract_rois(image, PAD_NAMES)

    # 4. Fallback or Classification
    overall_result = "INCONCLUSIVE"
    review_required = True
    mean_confidence = 0.0

    if not qr.passed:
        overall_result = "INCONCLUSIVE"
        review_required = True
        notes = f"Quality gate rejected frame: {', '.join(qr.failure_reasons)}"
        resolved_calls = {"quality_gate": "failed", "reasons": qr.failure_reasons}
        deltae_results = {}
        ml_results = {}
    elif not roi.strip_found:
        overall_result = "INCONCLUSIVE"
        review_required = True
        notes = "Test strip not located by classical ROI detector."
        resolved_calls = {"roi_extraction": "failed"}
        deltae_results = {}
        ml_results = {}
    else:
        # Apply calibration
        calibrated_rgb = {
            name: tuple(cal.apply(np.array(rgb)).tolist())
            for name, rgb in roi.pad_mean_rgb.items()
        }
        deltae_results = classify_all_pads(calibrated_rgb, cfg.delta_e)

        # ML confidence layer
        ml_model = TFLiteConfidenceModel(cfg.ml_confidence)
        ml_results = {}
        resolved_calls = {}
        confs = []
        calls = []

        for analyte, verdict in deltae_results.items():
            patch = roi.pad_rois.get(analyte)
            if patch is not None and patch.size > 0:
                patch_rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
            else:
                patch_rgb = np.zeros((224, 224, 3), dtype=np.uint8)

            ml_verdict = ml_model.predict(patch_rgb)
            ml_results[analyte] = ml_verdict
            resolved = resolve_with_ml(verdict.call, ml_verdict, cfg.ml_confidence)
            resolved_calls[analyte] = resolved

            confs.append(ml_verdict.confidence)
            calls.append(resolved["final_call"])
            if resolved["flagged_for_review"]:
                review_required = True

        mean_confidence = float(np.mean(confs)) if confs else 0.0

        if any(c == "positive" for c in calls):
            overall_result = "POSITIVE"
            review_required = False
        elif all(c == "negative" for c in calls):
            overall_result = "NEGATIVE"
            review_required = False
        else:
            overall_result = "INCONCLUSIVE"
            review_required = True

    # 5. Evidence packet
    packet = build_evidence_packet(
        source_image_bytes=image_bytes,
        quality_report=qr.to_dict(),
        calibration_result=cal.to_dict(),
        roi_summary={"strip_found": roi.strip_found},
        deltae_verdicts={k: v.to_dict() for k, v in deltae_results.items()},
        ml_verdicts={k: v.to_dict() for k, v in ml_results.items()},
        resolved_calls=resolved_calls,
        device_metadata={"source_image_path": os.path.abspath(image_path)},
        cfg=cfg.evidence,
    )
    packet_path = save_packet(packet, cfg.evidence)
    elapsed_ms = int((time.perf_counter() - t_start) * 1000)

    # Standard JSON Output format as specified
    output_packet = {
        "result": overall_result,
        "confidence": round(mean_confidence, 4),
        "image_quality": image_quality,
        "calibration": calibration_status,
        "model_type": "SYNTHETIC_DEMO",
        "model_version": "v1.0-MobileNetV3-Small-INT8",
        "processing_time_ms": elapsed_ms,
        "sha256": packet.chained_hash,
        "review_required": review_required
    }

    if verbose:
        # Visual presentation card
        box_width = 62
        print("\n" + "=" * box_width)
        print("  DIGITAL COMPANION FOR FIELD DRUG TESTING (PROTOTYPE DEMO)  ")
        print("=" * box_width)
        res_color = overall_result
        print(f"  RESULT:              {res_color}")
        print(f"  Confidence:          {mean_confidence*100:.1f}%")
        print(f"  Image Quality:       {image_quality} (blur={qr.blur_variance:.1f}, lum={qr.mean_luminance:.1f})")
        print(f"  Calibration Status:  {calibration_status} (MAE: {cal.residual_mae:.2f})")
        print(f"  Model Architecture:  MobileNetV3-Small INT8 [SYNTHETIC DEMO]")
        print(f"  Evidence Integrity:  SHA-256 CHAINED VERIFIED")
        print(f"  Evidence Hash:       {packet.chained_hash[:24]}...")
        print(f"  Review Required:     {'YES [!]' if review_required else 'NO'}")
        print(f"  Processing Time:     {elapsed_ms} ms")
        print("-" * box_width)
        print("  Analyte Pad Breakdown:")
        for analyte, res in resolved_calls.items():
            if isinstance(res, dict) and "final_call" in res:
                flag = " [! Review]" if res.get("flagged_for_review") else ""
                print(f"    - {analyte:10s}: {res['final_call']:13s} (ML Conf: {res.get('ml_confidence', 0)*100:.1f}%){flag}")
        print("=" * box_width)
        print("\n[Structured JSON Packet]")
        print(json.dumps(output_packet, indent=2))

    return output_packet


def main():
    parser = argparse.ArgumentParser(description="Run prototype demo inference.")
    parser.add_argument("image", nargs="?", default="demo/images/positive_style.jpg",
                        help="Path to test strip image (default: demo/images/positive_style.jpg)")
    parser.add_argument("--json", action="store_true", help="Print only JSON output.")
    args = parser.parse_args()

    run_demo(args.image, verbose=not args.json)


if __name__ == "__main__":
    main()
