#!/usr/bin/env python3
"""Evaluate locked Drug Companion predictions against reference results.

Input CSV columns:
sample_id,reference_label,prediction_label,confidence,site,device,batch,session
"""
from __future__ import annotations
import argparse, csv, json, random
from collections import defaultdict
from pathlib import Path

REF = {"positive", "negative", "invalid"}
PRED = {"positive", "negative", "invalid", "inconclusive"}

def safe(a, b):
    return None if b == 0 else a / b

def load_rows(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    required = {"sample_id", "reference_label", "prediction_label"}
    missing = required - set(rows[0]) if rows else required
    if missing:
        raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing)))
    seen = set()
    for r in rows:
        if r["sample_id"] in seen:
            raise ValueError("Duplicate sample_id: " + r["sample_id"])
        seen.add(r["sample_id"])
        if r["reference_label"] not in REF:
            raise ValueError("Invalid reference label: " + r["sample_id"])
        if r["prediction_label"] not in PRED:
            raise ValueError("Invalid prediction label: " + r["sample_id"])
    return rows

def counts(rows):
    tp = fp = tn = fn = 0
    for r in rows:
        ref, pred = r["reference_label"], r["prediction_label"]
        if ref == "positive":
            if pred == "positive": tp += 1
            elif pred in {"negative", "invalid"}: fn += 1
        elif ref == "negative":
            if pred == "positive": fp += 1
            elif pred in {"negative", "invalid"}: tn += 1
    return tp, fp, tn, fn

def bootstrap(rows, metric, iterations=2000):
    eligible = [r for r in rows if r["reference_label"] in {"positive", "negative"}]
    if not eligible:
        return None
    rng = random.Random(20260924)
    vals = []
    for _ in range(iterations):
        sample = [eligible[rng.randrange(len(eligible))] for _ in eligible]
        tp, fp, tn, fn = counts(sample)
        value = safe(tp, tp + fn) if metric == "sensitivity" else safe(tn, tn + fp)
        if value is not None: vals.append(value)
    if not vals: return None
    vals.sort()
    return [round(vals[max(0, int(len(vals)*0.025)-1)], 4),
            round(vals[min(len(vals)-1, int(len(vals)*0.975))], 4)]

def evaluate(rows, acceptance):
    total = len(rows)
    decided_rows = [r for r in rows if r["prediction_label"] in {"positive", "negative"}]
    tp, fp, tn, fn = counts(rows)
    sensitivity = safe(tp, tp + fn)
    specificity = safe(tn, tn + fp)
    ppv = safe(tp, tp + fp)
    npv = safe(tn, tn + fn)
    accuracy = safe(sum(r["prediction_label"] == r["reference_label"] for r in decided_rows), len(decided_rows))
    f1 = safe(2 * ppv * sensitivity, ppv + sensitivity) if ppv is not None and sensitivity is not None else None
    inconclusive = total - len(decided_rows)
    metrics = {
        "samples": total,
        "decided": len(decided_rows),
        "coverage": safe(len(decided_rows), total),
        "inconclusive_or_invalid_rate": safe(inconclusive, total),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "accuracy_decided": accuracy,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "ppv": ppv,
        "npv": npv,
        "f1_positive": f1,
        "sensitivity_ci95": bootstrap(rows, "sensitivity"),
        "specificity_ci95": bootstrap(rows, "specificity"),
    }
    checks = {}
    pairs = [
        ("minimum_test_samples", metrics["samples"], ">="),
        ("minimum_sensitivity", sensitivity, ">="),
        ("minimum_specificity", specificity, ">="),
        ("maximum_inconclusive_rate", metrics["inconclusive_or_invalid_rate"], "<="),
        ("minimum_coverage", metrics["coverage"], ">="),
    ]
    for key, value, op in pairs:
        threshold = acceptance.get(key)
        if threshold is not None and value is not None:
            checks[key] = value >= threshold if op == ">=" else value <= threshold
    metrics["acceptance_checks"] = checks
    metrics["acceptance_status"] = (
        "PASS" if checks and all(checks.values()) and acceptance.get("status") == "approved"
        else "NOT_ACCEPTED"
    )
    return metrics

def subgroup(rows, field):
    groups = defaultdict(list)
    for r in rows: groups[r.get(field) or "unknown"].append(r)
    result = {}
    for key, group in sorted(groups.items()):
        tp, fp, tn, fn = counts(group)
        result[key] = {
            "samples": len(group),
            "sensitivity": safe(tp, tp + fn),
            "specificity": safe(tn, tn + fp),
            "coverage": safe(sum(r["prediction_label"] in {"positive", "negative"} for r in group), len(group)),
        }
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("predictions", type=Path)
    p.add_argument("--acceptance", type=Path, default=Path(__file__).with_name("acceptance.json"))
    p.add_argument("--output", type=Path, default=Path("validation_report.json"))
    args = p.parse_args()
    rows = load_rows(args.predictions)
    acceptance = json.loads(args.acceptance.read_text(encoding="utf-8"))
    report = {
        "schema_version": "1.0.0",
        "evaluation_type": "target_prediction_evaluation",
        "metrics": evaluate(rows, acceptance),
        "subgroups": {
            "site": subgroup(rows, "site"),
            "device": subgroup(rows, "device"),
            "batch": subgroup(rows, "batch"),
        },
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
