import csv
import json
from pathlib import Path
import subprocess
import sys


def test_evaluator_produces_metrics(tmp_path):
    predictions = tmp_path / "predictions.csv"
    predictions.write_text(
        "sample_id,reference_label,prediction_label,confidence,site,device,batch,session\n"
        "s1,positive,positive,0.9,A,cam1,b1,s1\n"
        "s2,negative,negative,0.8,A,cam1,b1,s2\n"
        "s3,positive,negative,0.6,A,cam1,b1,s3\n"
        "s4,negative,positive,0.7,B,cam2,b2,s4\n",
        encoding="utf-8",
    )
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(
        json.dumps({
            "status": "approved",
            "minimum_test_samples": 4,
            "minimum_sensitivity": 0.5,
            "minimum_specificity": 0.5,
            "maximum_inconclusive_rate": 0.5,
            "minimum_coverage": 0.5,
        }),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    script = Path(__file__).parents[1] / "evaluate_predictions.py"
    result = subprocess.run(
        [sys.executable, str(script), str(predictions), "--acceptance", str(acceptance), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["metrics"]["samples"] == 4
    assert report["metrics"]["sensitivity"] == 0.5
    assert report["metrics"]["specificity"] == 0.5
    assert report["metrics"]["acceptance_status"] == "PASS"
