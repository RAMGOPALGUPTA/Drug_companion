#!/usr/bin/env python3
"""Run the real Drug Companion inference pipeline over the generated demo dataset.
Prototype/evaluation helper; never promotes the model to validated status.
"""
from __future__ import annotations
import argparse, csv
from pathlib import Path
from app.services.analysis_service import analyze_bytes

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("predictions.csv"))
    args = parser.parse_args()
    rows = list(csv.DictReader((args.dataset / "labels.csv").open("r", encoding="utf-8")))
    out = []
    for row in rows:
        data = (args.dataset / row["filename"]).read_bytes()
        result = analyze_bytes(data, filename=row["filename"], officer="dataset-runner", location="synthetic-demo", image_mime="image/jpeg")
        out.append({
            "sample_id": row["sample_id"],
            "reference_label": row["reference_label"],
            "prediction_label": result.get("result", "inconclusive"),
            "confidence": result.get("confidence", 0.0),
            "site": "synthetic",
            "device": "generated-demo",
            "batch": "generated_strip_demo_v1",
            "session": row["sample_id"],
        })
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)

if __name__ == "__main__":
    main()
