"""
Centralized CSV/JSON baseline logging for experiment tracking.

Every pipeline run (or batch eval run) appends one row to a CSV log and
one JSON record to a JSONL log, so accuracy / threshold-tuning
experiments (Phase 12) can be compared across runs without re-deriving
results from evidence packets each time.
"""
import csv
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


CSV_FIELDS = [
    "timestamp", "run_id", "image_path", "quality_passed", "calibration_passed",
    "calibration_residual_mae", "roi_found", "analyte", "deltae_call",
    "ml_label", "ml_confidence", "final_call", "resolution", "flagged_for_review",
]


@dataclass
class BaselineLogger:
    log_dir: str = "logs"
    csv_filename: str = "baseline_runs.csv"
    jsonl_filename: str = "baseline_runs.jsonl"

    def __post_init__(self):
        os.makedirs(self.log_dir, exist_ok=True)
        self._csv_path = os.path.join(self.log_dir, self.csv_filename)
        self._jsonl_path = os.path.join(self.log_dir, self.jsonl_filename)
        if not os.path.exists(self._csv_path):
            with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()

    def log_run(self, run_id: str, image_path: str, quality_report: dict,
                calibration_result: dict, roi_found: bool,
                deltae_verdicts: Dict[str, dict], ml_verdicts: Dict[str, dict],
                resolved_calls: Dict[str, dict]) -> None:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

        full_record = {
            "timestamp": timestamp, "run_id": run_id, "image_path": image_path,
            "quality_report": quality_report, "calibration_result": calibration_result,
            "roi_found": roi_found, "deltae_verdicts": deltae_verdicts,
            "ml_verdicts": ml_verdicts, "resolved_calls": resolved_calls,
        }
        with open(self._jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(full_record, default=str) + "\n")

        rows = []
        for analyte, resolved in resolved_calls.items():
            if not isinstance(resolved, dict) or "final_call" not in resolved:
                continue
            deltae = deltae_verdicts.get(analyte, {})
            ml = ml_verdicts.get(analyte, {})
            rows.append({
                "timestamp": timestamp, "run_id": run_id, "image_path": image_path,
                "quality_passed": quality_report.get("passed"),
                "calibration_passed": calibration_result.get("passed"),
                "calibration_residual_mae": calibration_result.get("residual_mae"),
                "roi_found": roi_found, "analyte": analyte,
                "deltae_call": deltae.get("call"),
                "ml_label": ml.get("label"), "ml_confidence": ml.get("confidence"),
                "final_call": resolved.get("final_call"),
                "resolution": resolved.get("resolution"),
                "flagged_for_review": resolved.get("flagged_for_review"),
            })

        if rows:
            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                for row in rows:
                    writer.writerow(row)

    def load_all_runs(self) -> List[dict]:
        if not os.path.exists(self._jsonl_path):
            return []
        with open(self._jsonl_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
