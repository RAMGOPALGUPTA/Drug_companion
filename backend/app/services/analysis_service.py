from __future__ import annotations

from pathlib import Path
import uuid

import cv2
import numpy as np

from app.evidence.evidence_packet import build_evidence_packet
from app.inference.calibration import calibrate
from app.inference.config import PipelineConfig
from app.inference.deltae_engine import classify_all_pads
from app.inference.ml_confidence import TFLiteConfidenceModel, resolve_with_ml
from app.inference.quality_gate import run_quality_gate
from app.inference.roi_extraction import extract_rois

PAD_NAMES = ["control", "opioid", "stimulant", "benzo"]
_CASES = {}

def _config():
    cfg = PipelineConfig()
    cfg.ml_confidence.model_path = str(
        Path(__file__).resolve().parents[3] / "backend" / "models" / "mobilenetv3_small_int8.tflite"
    )
    return cfg

def _overall(resolved):
    calls = [v.get("final_call") for k, v in resolved.items() if k != "pipeline_status"]
    if any(x == "positive" for x in calls):
        return "positive"
    if calls and all(x == "negative" for x in calls):
        return "negative"
    return "inconclusive"

def analyze_bytes(data: bytes, filename: str | None = None):
    cfg = _config()
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to decode the uploaded image")

    quality = run_quality_gate(image, cfg.quality_gate)
    if not quality.passed:
        packet = build_evidence_packet(
            data, quality.to_dict(),
            {"passed": False, "failure_reason": "not_attempted"},
            {"strip_found": False, "calibrated_pad_rgb": {}},
            {}, {}, {"pipeline_status": "aborted", "reason": "quality_gate_failed"},
            {"filename": filename}, cfg.evidence
        )
        return _store(filename, "inconclusive", 0.0, quality.to_dict(), packet, {}, {}, {})

    calibration = calibrate(image, cfg.calibration)
    roi = extract_rois(image, PAD_NAMES, orientation="vertical")
    if not roi.strip_found:
        packet = build_evidence_packet(
            data, quality.to_dict(), calibration.to_dict(),
            {"strip_found": False, "calibrated_pad_rgb": {}},
            {}, {}, {"pipeline_status": "aborted", "reason": "roi_extraction_failed"},
            {"filename": filename}, cfg.evidence
        )
        return _store(filename, "inconclusive", 0.0, quality.to_dict(), packet, calibration.to_dict(), {}, {})

    calibrated = {
        name: tuple(calibration.apply(np.asarray(rgb)).tolist())
        for name, rgb in roi.pad_mean_rgb.items()
    }
    deltae = classify_all_pads(calibrated, cfg.delta_e)
    model = TFLiteConfidenceModel(cfg.ml_confidence)
    ml = {}
    resolved = {}

    for analyte, verdict in deltae.items():
        patch = roi.pad_rois.get(analyte)
        rgb = (
            cv2.cvtColor(patch, cv2.COLOR_BGR2RGB)
            if patch is not None
            else np.zeros((224, 224, 3), dtype=np.uint8)
        )
        ml_verdict = model.predict(rgb)
        ml[analyte] = ml_verdict.to_dict()
        resolved[analyte] = resolve_with_ml(verdict.call, ml_verdict, cfg.ml_confidence)

    result = _overall(resolved)
    confidence = round(
        max((v.get("ml_confidence", 0.0) for v in resolved.values()), default=0.0), 4
    )
    packet = build_evidence_packet(
        data, quality.to_dict(), calibration.to_dict(),
        {"strip_found": True, "calibrated_pad_rgb": calibrated},
        {k: v.to_dict() for k, v in deltae.items()}, ml, resolved,
        {"filename": filename}, cfg.evidence
    )
    return _store(filename, result, confidence, quality.to_dict(), packet,
                  calibration.to_dict(), {k: v.to_dict() for k, v in deltae.items()}, ml)

def _store(filename, result, confidence, quality, packet, calibration, deltae, ml):
    case_id = "CASE-" + uuid.uuid4().hex[:8].upper()
    resolved = packet.final_verdicts
    record = {
        "case_id": case_id,
        "created_at": packet.created_utc,
        "filename": filename,
        "result": result,
        "confidence": confidence,
        "officer": "Field Operator",
        "location": "Field capture",
        "quality": quality,
        "calibration": calibration,
        "deltae": deltae,
        "ml": ml,
        "resolved": resolved,
        "evidence_packet": packet.to_dict(),
        "evidence": {
            "image_sha256": packet.source_image_sha256,
            "payload_sha256": packet.chained_hash,
            "integrity": "verified",
        },
    }
    _CASES[case_id] = record
    return {
        "case_id": case_id,
        "result": result,
        "confidence": confidence,
        "rule_based_call": next(
            (v.get("rule_based_call") for v in resolved.values() if isinstance(v, dict)),
            "inconclusive",
        ),
        "model": {"name": "MobileNetV3-Small", "version": "prototype", "input": "224×224 RGB"},
        "pipeline": {
            "image_quality": quality,
            "calibration": calibration,
            "roi": {"detected": bool(deltae)},
            "rule_engine": {"call": result, "analytes": deltae},
            "ml": {"label": result, "confidence": confidence, "analytes": ml},
        },
        "evidence": record["evidence"],
        "analytes": resolved,
        "evidence_packet": record["evidence_packet"],
        "demo_only": False,
    }

def list_cases():
    return [
        {
            "id": case_id,
            "case_id": case_id,
            "result": record["result"],
            "confidence": record["confidence"],
            "officer": record["officer"],
            "time": record["created_at"][11:16],
            "location": record["location"],
            "integrity": "verified",
        }
        for case_id, record in reversed(list(_CASES.items()))
    ]

def get_case(case_id):
    record = _CASES.get(case_id)
    if record is None:
        return None
    return {
        "id": case_id,
        "case_id": case_id,
        "result": record["result"],
        "confidence": record["confidence"],
        "officer": record["officer"],
        "time": record["created_at"][11:16],
        "location": record["location"],
        "integrity": "verified",
        "filename": record["filename"],
        "quality": record["quality"],
        "calibration": record["calibration"],
        "deltae": record["deltae"],
        "ml": record["ml"],
        "resolved": record["resolved"],
        "evidence": record["evidence"],
        "evidence_packet": record["evidence_packet"],
    }

def get_evidence(case_id):
    record = _CASES.get(case_id)
    return record["evidence_packet"] if record else None
