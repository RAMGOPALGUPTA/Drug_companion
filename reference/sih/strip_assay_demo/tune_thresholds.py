#!/usr/bin/env python3
"""
tune_thresholds.py — Phase 12: tune Delta-E and ML confidence thresholds
against a labeled batch of images for your specific kit.

Expects a directory of images plus a manifest.json (as produced by
sample_data/synthetic_generator.generate_dataset, or hand-labeled real
kit photos in the same format):

    [
      {"file": "img_0001.jpg", "positive_analytes": ["opioid"]},
      {"file": "img_0002.jpg", "positive_analytes": []},
      ...
    ]

For each candidate confident_match_threshold / confident_nonmatch_threshold
pair, runs the pipeline over the labeled set and reports accuracy,
false-positive rate, false-negative rate, and inconclusive rate, so you
can pick thresholds that fit your kit's evidentiary risk tolerance.

Usage:
    python tune_thresholds.py --data-dir sample_data/tuning_set
"""
import argparse
import copy
import json
import os
from typing import List, Dict

import cv2

from core.config import DEFAULT_CONFIG
from core.quality_gate import run_quality_gate
from core.calibration import calibrate
from core.roi_extraction import extract_rois
from core.deltae_engine import classify_all_pads


ANALYTES = ["opioid", "stimulant", "benzo"]


def load_manifest(data_dir: str) -> List[dict]:
    manifest_path = os.path.join(data_dir, "manifest.json")
    with open(manifest_path, "r") as f:
        return json.load(f)


def evaluate_thresholds(data_dir: str, match_thresh: float, nonmatch_thresh: float) -> Dict[str, float]:
    manifest = load_manifest(data_dir)
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.delta_e.confident_match_threshold = match_thresh
    cfg.delta_e.confident_nonmatch_threshold = nonmatch_thresh

    tp = fp = tn = fn = inconclusive = total = 0

    for entry in manifest:
        image_path = os.path.join(data_dir, entry["file"])
        image = cv2.imread(image_path)
        if image is None:
            continue

        qr = run_quality_gate(image, cfg.quality_gate)
        if not qr.passed:
            continue

        cal = calibrate(image, cfg.calibration)
        roi = extract_rois(image, ["control", "opioid", "stimulant", "benzo"])
        if not roi.strip_found:
            continue

        calibrated_rgb = {
            name: tuple(cal.apply(__import__("numpy").array(rgb)).tolist())
            for name, rgb in roi.pad_mean_rgb.items()
        }
        results = classify_all_pads(calibrated_rgb, cfg.delta_e)

        ground_truth_positive = set(entry.get("positive_analytes", []))

        for analyte in ANALYTES:
            if analyte not in results:
                continue
            call = results[analyte].call
            is_gt_positive = analyte in ground_truth_positive
            total += 1

            if call == "inconclusive":
                inconclusive += 1
            elif call == "positive" and is_gt_positive:
                tp += 1
            elif call == "positive" and not is_gt_positive:
                fp += 1
            elif call == "negative" and not is_gt_positive:
                tn += 1
            elif call == "negative" and is_gt_positive:
                fn += 1

    decided = tp + fp + tn + fn
    accuracy = (tp + tn) / decided if decided else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    inconclusive_rate = inconclusive / total if total else 0.0

    return {
        "match_thresh": match_thresh, "nonmatch_thresh": nonmatch_thresh,
        "total_pad_evals": total, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "inconclusive": inconclusive, "accuracy_on_decided": round(accuracy, 4),
        "false_positive_rate": round(fpr, 4), "false_negative_rate": round(fnr, 4),
        "inconclusive_rate": round(inconclusive_rate, 4),
    }


def grid_search(data_dir: str, match_range, nonmatch_range) -> List[dict]:
    results = []
    for m in match_range:
        for n in nonmatch_range:
            if n <= m:
                continue
            results.append(evaluate_thresholds(data_dir, m, n))
    return results


def main():
    parser = argparse.ArgumentParser(description="Tune Delta-E thresholds for your kit.")
    parser.add_argument("--data-dir", type=str, required=True,
                         help="Directory with labeled images + manifest.json")
    parser.add_argument("--match-min", type=float, default=2.0)
    parser.add_argument("--match-max", type=float, default=8.0)
    parser.add_argument("--nonmatch-min", type=float, default=8.0)
    parser.add_argument("--nonmatch-max", type=float, default=20.0)
    parser.add_argument("--step", type=float, default=2.0)
    parser.add_argument("--optimize-for", type=str, default="false_negative_rate",
                         choices=["accuracy_on_decided", "false_negative_rate",
                                  "false_positive_rate", "inconclusive_rate"])
    args = parser.parse_args()

    match_range = _frange(args.match_min, args.match_max, args.step)
    nonmatch_range = _frange(args.nonmatch_min, args.nonmatch_max, args.step)

    results = grid_search(args.data_dir, match_range, nonmatch_range)

    # For evidentiary use, minimizing false negatives (missed positives) is
    # usually the priority; sort accordingly but show full table.
    reverse = args.optimize_for == "accuracy_on_decided"
    results.sort(key=lambda r: r[args.optimize_for], reverse=reverse)

    print(f"{'match':>6} {'nonmatch':>9} {'n':>5} {'acc':>7} {'FPR':>7} {'FNR':>7} {'inconcl%':>9}")
    for r in results:
        print(f"{r['match_thresh']:>6.1f} {r['nonmatch_thresh']:>9.1f} {r['total_pad_evals']:>5} "
              f"{r['accuracy_on_decided']:>7.3f} {r['false_positive_rate']:>7.3f} "
              f"{r['false_negative_rate']:>7.3f} {r['inconclusive_rate']:>9.3f}")

    if results:
        best = results[0]
        print(f"\nBest by {args.optimize_for}: match={best['match_thresh']}, "
              f"nonmatch={best['nonmatch_thresh']}")
        print("Update core/config.py DeltaEConfig.confident_match_threshold / "
              "confident_nonmatch_threshold with these values.")


def _frange(start, stop, step):
    vals = []
    v = start
    while v <= stop + 1e-9:
        vals.append(round(v, 4))
        v += step
    return vals


if __name__ == "__main__":
    main()
