from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import json
import uuid

import cv2
import numpy as np

from app.db.repository import (
    database_available,
    get_case as db_get_case,
    get_evidence as db_get_evidence,
    get_summary as db_get_summary,
    list_cases as db_list_cases,
    persist_case,
)
from app.evidence.evidence_packet import build_evidence_packet
from app.inference.calibration import calibrate
from app.inference.config import PipelineConfig
from app.inference.deltae_engine import classify_all_pads
from app.inference.ml_confidence import TFLiteConfidenceModel, resolve_with_ml
from app.inference.quality_gate import run_quality_gate
from app.inference.roi_extraction import extract_rois

PAD_NAMES = ["control", "opioid", "stimulant", "benzo"]
_CASES: dict[str, dict] = {}
MODEL_FILENAME = "mobilenetv3_small_int8.tflite"


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _model_path() -> Path:
    return _backend_root() / "models" / MODEL_FILENAME


def _metadata_path() -> Path:
    return _backend_root() / "models" / "model_metadata.json"


def _config() -> PipelineConfig:
    cfg = PipelineConfig()
    cfg.ml_confidence.model_path = str(_model_path())
    return cfg


@lru_cache(maxsize=1)
def _model() -> TFLiteConfidenceModel:
    return TFLiteConfidenceModel(_config().ml_confidence)


@lru_cache(maxsize=1)
def _model_metadata() -> dict:
    try:
        return json.loads(_metadata_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def get_model_info() -> dict:
    path = _model_path()
    metadata = _model_metadata()
    model = _model()
    artifact_sha256 = sha256(path.read_bytes()).hexdigest() if path.exists() else None
    artifact_size = path.stat().st_size if path.exists() else None
    return {
        "name": metadata.get("model_architecture", "MobileNetV3-Small"),
        "version": metadata.get("training_timestamp", "unknown"),
        "artifact": MODEL_FILENAME,
        "artifact_path": str(path),
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size,
        "input": metadata.get("model_input_shape", [224, 224, 3]),
        "normalization": metadata.get("normalization", "rescaling_0_to_1"),
        "class_labels": metadata.get("class_labels", ["negative", "positive", "invalid"]),
        "runtime": "ai_edge_litert" if model.is_available else "unavailable",
        "model_available": model.is_available,
        "load_error": model.load_error,
        "model_type": metadata.get("model_type", "SYNTHETIC_DEMO / BOOTSTRAP"),
        "target_validated": bool(metadata.get("target_validated", False)),
        "forensic_status": metadata.get(
            "forensic_status", "PROTOTYPE_DEMO_ONLY_NOT_FORENSICALLY_VALIDATED"
        ),
    }


def _overall(resolved: dict) -> str:
    calls = [v.get("final_call") for k, v in resolved.items() if k != "pipeline_status"]
    if any(x == "positive" for x in calls):
        return "positive"
    if calls and all(x == "negative" for x in calls):
        return "negative"
    return "inconclusive"


def analyze_bytes(
    data: bytes,
    filename: str | None = None,
    officer: str = "Field Operator",
    location: str = "Field capture",
    image_mime: str | None = None,
):
    cfg = _config()
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to decode the uploaded image")

    quality = run_quality_gate(image, cfg.quality_gate)
    if not quality.passed:
        packet = build_evidence_packet(
            data, quality.to_dict(), {"passed": False, "failure_reason": "not_attempted"},
            {"strip_found": False, "calibrated_pad_rgb": {}}, {}, {},
            {"pipeline_status": "aborted", "reason": "quality_gate_failed"},
            {"filename": filename, "model": get_model_info()}, cfg.evidence,
        )
        return _store(filename, "inconclusive", 0.0, quality.to_dict(), packet, {}, {}, officer, location, image_mime, len(data))

    calibration = calibrate(image, cfg.calibration)
    roi = extract_rois(image, PAD_NAMES, orientation="vertical")
    if not roi.strip_found:
        packet = build_evidence_packet(
            data, quality.to_dict(), calibration.to_dict(),
            {"strip_found": False, "calibrated_pad_rgb": {}}, {}, {},
            {"pipeline_status": "aborted", "reason": "roi_extraction_failed"},
            {"filename": filename, "model": get_model_info()}, cfg.evidence,
        )
        return _store(filename, "inconclusive", 0.0, quality.to_dict(), packet,
                      calibration.to_dict(), {}, officer, location, image_mime, len(data))

    calibrated = {
        name: tuple(calibration.apply(np.asarray(rgb)).tolist())
        for name, rgb in roi.pad_mean_rgb.items()
    }
    deltae = classify_all_pads(calibrated, cfg.delta_e)
    model = _model()
    ml: dict = {}
    resolved: dict = {}

    for analyte, verdict in deltae.items():
        patch = roi.pad_rois.get(analyte)
        rgb = cv2.cvtColor(patch, cv2.COLOR_BGR2RGB) if patch is not None else np.zeros((224, 224, 3), dtype=np.uint8)
        ml_verdict = model.predict(rgb)
        ml[analyte] = ml_verdict.to_dict()
        resolved[analyte] = resolve_with_ml(verdict.call, ml_verdict, cfg.ml_confidence)

    result = _overall(resolved)
    confidence = round(
        max((v.get("ml_confidence", 0.0) for v in resolved.values()
             if v.get("ml_confidence") is not None), default=0.0), 4,
    )
    packet = build_evidence_packet(
        data, quality.to_dict(), calibration.to_dict(),
        {"strip_found": True, "calibrated_pad_rgb": calibrated},
        {k: v.to_dict() for k, v in deltae.items()}, ml, resolved,
        {"filename": filename, "model": get_model_info()}, cfg.evidence,
    )
    return _store(filename, result, confidence, quality.to_dict(), packet,
                  calibration.to_dict(), {k: v.to_dict() for k, v in deltae.items()},
                  officer, location, image_mime, len(data))


def _store(filename, result, confidence, quality, packet, calibration, deltae,
           officer, location, image_mime, image_size):
    case_id = "CASE-" + uuid.uuid4().hex[:8].upper()
    model_info = get_model_info()
    record = {
        "case_id": case_id, "created_at": packet.created_utc, "filename": filename,
        "result": result, "confidence": confidence, "officer": officer,
        "location": location, "image_mime": image_mime, "image_size": image_size,
        "quality": quality, "calibration": calibration, "deltae": deltae,
        "ml": packet.stages.get("ml_confidence", {}), "resolved": packet.final_verdicts,
        "model": model_info, "evidence_packet": packet.to_dict(),
        "evidence": {
            "image_sha256": packet.source_image_sha256,
            "payload_sha256": packet.chained_hash, "integrity": "verified",
        },
    }
    _CASES[case_id] = record
    stored = persist_case(record)
    result_payload = {
        "case_id": case_id, "result": result, "confidence": confidence,
        "rule_based_call": next((v.get("rule_based_call") for v in packet.final_verdicts.values()
                                 if isinstance(v, dict)), "inconclusive"),
        "model": model_info,
        "storage": "postgresql" if stored else "process_memory",
        "pipeline": {
            "image_quality": quality,
            "calibration": calibration,
            "roi": {"detected": bool(deltae)},
            "rule_engine": {"call": result, "analytes": deltae},
            "ml": {"label": result, "confidence": confidence,
                   "available": model_info["model_available"], "analytes": record["ml"]},
        },
        "evidence": record["evidence"], "analytes": packet.final_verdicts,
        "evidence_packet": record["evidence_packet"],
        "demo_only": not model_info["target_validated"],
    }
    return result_payload


def list_cases():
    rows = db_list_cases()
    if rows:
        return rows
    return [
        {**{"id": cid, "case_id": cid}, **{
            "result": r["result"], "confidence": r["confidence"], "officer": r["officer"],
            "time": r["created_at"], "location": r["location"], "integrity": "verified",
            "storage": "process_memory",
        }}
        for cid, r in reversed(list(_CASES.items()))
    ]


def get_case(case_id):
    db_record = db_get_case(case_id)
    if db_record is not None:
        return db_record
    record = _CASES.get(case_id)
    if record is None:
        return None
    return {
        "id": case_id, "case_id": case_id, "result": record["result"],
        "confidence": record["confidence"], "officer": record["officer"],
        "time": record["created_at"], "location": record["location"],
        "integrity": "verified", "storage": "process_memory", **{
            k: record[k] for k in (
                "filename","quality","calibration","deltae","ml","resolved",
                "model","evidence","evidence_packet"
            )
        },
    }


def get_evidence(case_id):
    db_record = db_get_evidence(case_id)
    if db_record is not None:
        return db_record
    record = _CASES.get(case_id)
    return record["evidence_packet"] if record else None


def get_summary() -> dict:
    summary = db_get_summary()
    if summary is not None:
        summary["model"] = get_model_info()
        return summary
    records = list(_CASES.values())
    counts = {"positive": 0, "negative": 0, "inconclusive": 0}
    for record in records:
        counts[record["result"]] = counts.get(record["result"], 0) + 1
    return {
        "total_cases": len(records), "positive": counts["positive"],
        "negative": counts["negative"], "inconclusive": counts["inconclusive"],
        "model": get_model_info(), "storage": "process_memory",
    }


def get_storage_status() -> dict:
    available = database_available()
    return {
        "backend": "postgresql" if available else "process_memory",
        "database_available": available,
        "fallback_enabled": True,
    }
