#!/usr/bin/env python3
"""
demo_run.py — End-to-end pipeline orchestration for a single test-strip image.

Pipeline stages:
  1. Load image
  2. Quality gate (blur / exposure)
  3. Reference-card calibration (3x3 matrix fit)
  4. Apply calibration + extract pad ROIs
  5. Delta-E (CIEDE2000) rule-based classification per analyte
  6. ML confidence layer (TFLite) to resolve inconclusive calls / flag disagreement
  7. Build + save tamper-evident evidence packet (SHA-256 chained)

Usage:
    python demo_run.py --image sample_data/example_strip.jpg
    python demo_run.py --image sample_data/example_strip.jpg --synthetic  # generate a synthetic test image first
"""
import argparse
import json
import sys
import os

import numpy as np
import cv2

from core.config import DEFAULT_CONFIG
from core.quality_gate import run_quality_gate
from core.calibration import calibrate
from core.roi_extraction import extract_rois
from core.deltae_engine import classify_all_pads
from core.ml_confidence import TFLiteConfidenceModel, resolve_with_ml
from core.baseline_logger import BaselineLogger
from evidence.evidence_packet import build_evidence_packet, save_packet

PAD_NAMES = ["control", "opioid", "stimulant", "benzo"]


def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {path}")
    return img


def run_pipeline(image_path: str, verbose: bool = True) -> dict:
    cfg = DEFAULT_CONFIG
    image = load_image(image_path)
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # --- 1. Quality gate ---------------------------------------------------
    qr = run_quality_gate(image, cfg.quality_gate)
    if verbose:
        print(f"[1/6] Quality gate: {'PASS' if qr.passed else 'FAIL'} "
              f"(blur_var={qr.blur_variance:.1f}, mean_lum={qr.mean_luminance:.1f})")
    if not qr.passed:
        if verbose:
            print(f"      Reasons: {qr.failure_reasons}")
            print("      Aborting: image quality insufficient for evidentiary analysis.")
        return _early_exit_packet(image_bytes, qr, cfg, "quality_gate_failed")

    # --- 2. Calibration ------------------------------------------------------
    cal = calibrate(image, cfg.calibration)
    if verbose:
        status = "PASS" if cal.passed else "FAIL"
        print(f"[2/6] Calibration: {status} (patches={cal.patch_count}, "
              f"residual_mae={cal.residual_mae:.2f})")
    if not cal.passed:
        if verbose:
            print(f"      Reason: {cal.failure_reason}")
            print("      Proceeding with identity matrix (uncalibrated) — flagged in evidence.")

    # --- 3. ROI extraction + apply calibration --------------------------------
    roi = extract_rois(image, PAD_NAMES, orientation="vertical")
    if verbose:
        print(f"[3/6] ROI extraction: {'PASS' if roi.strip_found else 'FAIL'} "
              f"({len(roi.pad_mean_rgb)}/{len(PAD_NAMES)} pads located)")
    if not roi.strip_found:
        if verbose:
            print(f"      Reason: {roi.failure_reason}")
            print("      Aborting: could not locate test strip pads.")
        return _early_exit_packet(image_bytes, qr, cfg, "roi_extraction_failed", calibration=cal)

    calibrated_rgb = {
        name: tuple(cal.apply(np.array(rgb)).tolist())
        for name, rgb in roi.pad_mean_rgb.items()
    }

    # --- 4. Delta-E classification -------------------------------------------
    deltae_results = classify_all_pads(calibrated_rgb, cfg.delta_e)
    if verbose:
        print("[4/6] Delta-E classification:")
        for analyte, v in deltae_results.items():
            print(f"      {analyte:12s} -> {v.call:13s} ({v.explanation})")

    # --- 5. ML confidence layer -----------------------------------------------
    ml_model = TFLiteConfidenceModel(cfg.ml_confidence)
    if verbose:
        avail = "loaded" if ml_model.is_available else "NOT loaded (falling back to rule-based only)"
        print(f"[5/6] ML confidence model: {avail}")

    ml_results = {}
    resolved_calls = {}
    for analyte, verdict in deltae_results.items():
        patch = roi.pad_rois.get(analyte)
        if patch is not None:
            patch_rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
        else:
            patch_rgb = np.zeros((224, 224, 3), dtype=np.uint8)
        ml_verdict = ml_model.predict(patch_rgb)
        ml_results[analyte] = ml_verdict
        resolved = resolve_with_ml(verdict.call, ml_verdict, cfg.ml_confidence)
        resolved_calls[analyte] = resolved
        if verbose:
            flag = " [!] FLAGGED FOR REVIEW" if resolved["flagged_for_review"] else ""
            print(f"      {analyte:12s} -> final: {resolved['final_call']:13s} "
                  f"[{resolved['resolution']}]{flag}")

    # --- 6. Evidence packet ---------------------------------------------------
    packet = build_evidence_packet(
        source_image_bytes=image_bytes,
        quality_report=qr.to_dict(),
        calibration_result=cal.to_dict(),
        roi_summary={"strip_found": roi.strip_found, "calibrated_pad_rgb": calibrated_rgb},
        deltae_verdicts={k: v.to_dict() for k, v in deltae_results.items()},
        ml_verdicts={k: v.to_dict() for k, v in ml_results.items()},
        resolved_calls=resolved_calls,
        device_metadata={"source_image_path": os.path.abspath(image_path)},
        cfg=cfg.evidence,
    )
    packet_path = save_packet(packet, cfg.evidence)
    if verbose:
        print(f"[6/6] Evidence packet saved: {packet_path}")
        print(f"      Chained SHA-256: {packet.chained_hash}")

    logger = BaselineLogger()
    logger.log_run(
        run_id=packet.packet_id, image_path=os.path.abspath(image_path),
        quality_report=qr.to_dict(), calibration_result=cal.to_dict(),
        roi_found=roi.strip_found,
        deltae_verdicts={k: v.to_dict() for k, v in deltae_results.items()},
        ml_verdicts={k: v.to_dict() for k, v in ml_results.items()},
        resolved_calls=resolved_calls,
    )

    return {"packet_path": packet_path, "resolved_calls": resolved_calls}


def _early_exit_packet(image_bytes, qr, cfg, reason, calibration=None):
    """Still generate an evidence packet on early abort, for auditability."""
    from core.calibration import CalibrationResult
    import numpy as np
    cal_dict = calibration.to_dict() if calibration else CalibrationResult(
        matrix=np.eye(3), residual_mae=float("inf"), patch_count=0,
        passed=False, failure_reason="not_attempted"
    ).to_dict()

    packet = build_evidence_packet(
        source_image_bytes=image_bytes,
        quality_report=qr.to_dict(),
        calibration_result=cal_dict,
        roi_summary={"strip_found": False, "calibrated_pad_rgb": {}},
        deltae_verdicts={},
        ml_verdicts={},
        resolved_calls={"pipeline_status": "aborted", "reason": reason},
        device_metadata={"aborted_reason": reason},
        cfg=cfg.evidence,
    )
    path = save_packet(packet, cfg.evidence)
    return {"packet_path": path, "resolved_calls": {"pipeline_status": "aborted", "reason": reason}}


def generate_synthetic_test_image(out_path: str, seed: int = 42) -> str:
    """Generate a synthetic reference-card + strip image for pipeline smoke-testing."""
    from sample_data.synthetic_generator import generate_synthetic_frame
    frame = generate_synthetic_frame(seed=seed)
    cv2.imwrite(out_path, frame)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Run the colorimetric assay pipeline end-to-end.")
    parser.add_argument("--image", type=str, default="sample_data/example_strip.jpg",
                         help="Path to input image.")
    parser.add_argument("--synthetic", action="store_true",
                         help="Generate a synthetic test image at --image path before running.")
    parser.add_argument("--json-out", type=str, default=None,
                         help="Optional path to dump the final resolved_calls as JSON.")
    args = parser.parse_args()

    if args.synthetic:
        os.makedirs(os.path.dirname(args.image) or ".", exist_ok=True)
        generate_synthetic_test_image(args.image)
        print(f"Generated synthetic test image at {args.image}\n")

    if not os.path.exists(args.image):
        print(f"ERROR: image not found at {args.image}. Use --synthetic to generate a test image.")
        sys.exit(1)

    result = run_pipeline(args.image)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(result["resolved_calls"], f, indent=2, default=str)
        print(f"\nResolved calls written to {args.json_out}")

    print("\n=== FINAL RESULT ===")
    print(json.dumps(result["resolved_calls"], indent=2, default=str))


if __name__ == "__main__":
    main()
