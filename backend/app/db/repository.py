from __future__ import annotations

import os
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DEFAULT_DATABASE_URL = "postgresql://drug_companion:drug_companion_dev@localhost:5432/drug_companion"


def ensure_schema_compatibility() -> None:
    with _connect() as conn:
        conn.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT 'Field capture'")


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _connect():
    return psycopg.connect(database_url(), row_factory=dict_row)


def persist_case(record: dict[str, Any]) -> bool:
    """Persist a completed analysis transactionally; return False if DB is unavailable."""
    try:
        case_uuid = _case_uuid(record["case_id"])
        model = record["model"]
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO operators(id, display_name) VALUES (%s,%s) "
                    "ON CONFLICT (id) DO NOTHING",
                    ("demo-operator", record["officer"]),
                )
                cur.execute(
                    """
                    INSERT INTO model_registry (
                        model_name, model_version, artifact_path, artifact_sha256,
                        architecture, model_format, quantization, input_width,
                        input_height, channels, normalization, class_labels,
                        model_type, target_validated, production_approved,
                        forensic_status, metadata
                    ) VALUES (
                        %s,%s,%s,%s,%s,'tflite','int8',%s,%s,%s,%s,%s,%s,%s,FALSE,%s,%s
                    )
                    ON CONFLICT (model_name, model_version) DO UPDATE SET
                        artifact_sha256=EXCLUDED.artifact_sha256,
                        metadata=EXCLUDED.metadata,
                        active=TRUE
                    """,
                    (
                        model["name"], model["version"], model["artifact_path"],
                        model["artifact_sha256"] or "0" * 64,
                        model["input"][0], model["input"][1], model["input"][2],
                        model["normalization"], Jsonb(model["class_labels"]),
                        "bootstrap" if not model["target_validated"] else "target_validated",
                        model["target_validated"], model["forensic_status"], Jsonb(model),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO cases (
                        id,case_reference,operator_id,classification,confidence,
                        location,captured_at,model_version,app_version,sync_status
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'synced')
                    ON CONFLICT (id) DO UPDATE SET
                        classification=EXCLUDED.classification, confidence=EXCLUDED.confidence
                    """,
                    (
                        case_uuid, record["case_id"], "demo-operator", record["result"],
                        record["confidence"], record.get("location") or "Field capture", record["created_at"], model["version"],
                        os.getenv("APP_VERSION", "0.3.0"),
                    ),
                )
                cur.execute(
                    "SELECT id FROM model_registry WHERE model_name=%s AND model_version=%s",
                    (model["name"], model["version"]),
                )
                model_row = cur.fetchone()
                model_id = model_row["id"] if model_row else None
                cur.execute(
                    """
                    INSERT INTO analysis_runs (
                        case_id,model_registry_id,pipeline_version,status,
                        final_classification,final_confidence,ml_classification,ml_confidence,
                        quality_gate,calibration,roi_extraction,rule_engine,ml_inference,
                        arbitration,completed_at
                    ) VALUES (
                        %s,%s,%s,'completed',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()
                    )
                    """,
                    (
                        case_uuid, model_id, os.getenv("PIPELINE_VERSION", "1.0.0"),
                        record["result"], record["confidence"], _overall_ml(record["ml"]),
                        _max_ml_confidence(record["ml"]), Jsonb(record["quality"]),
                        Jsonb(record["calibration"]), Jsonb({"detected": bool(record["deltae"])}),
                        Jsonb(record["deltae"]), Jsonb(record["ml"]), Jsonb(record["resolved"]),
                    ),
                )
                cur.execute(
                    "SELECT id FROM analysis_runs WHERE case_id=%s ORDER BY created_at DESC LIMIT 1",
                    (case_uuid,),
                )
                run_row = cur.fetchone()
                run_id = run_row["id"] if run_row else None
                cur.execute(
                    """
                    INSERT INTO evidence (
                        case_id,analysis_run_id,image_sha256,payload_sha256,
                        evidence_packet_sha256,image_size,image_mime,schema_version,
                        integrity_status,packet
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'verified',%s)
                    ON CONFLICT (case_id) DO UPDATE SET
                        packet=EXCLUDED.packet,payload_sha256=EXCLUDED.payload_sha256
                    """,
                    (
                        case_uuid, run_id, record["evidence"]["image_sha256"],
                        record["evidence"]["payload_sha256"], record["evidence"]["payload_sha256"],
                        record.get("image_size"), record.get("image_mime"),
                        record["evidence_packet"]["schema_version"], Jsonb(record["evidence_packet"]),
                    ),
                )
                cur.execute(
                    "INSERT INTO audit_log(case_id,operator_id,action,details) VALUES (%s,%s,%s,%s)",
                    (case_uuid, "demo-operator", "analysis.completed",
                     Jsonb({"case_id": record["case_id"]})),
                )
        return True
    except Exception:
        return False


def list_cases() -> list[dict[str, Any]]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT case_reference AS case_id, classification AS result, confidence,
                       o.display_name AS officer, captured_at, sync_status
                FROM cases c JOIN operators o ON o.id=c.operator_id
                ORDER BY captured_at DESC
                """
            ).fetchall()
        return [
            {
                "id": r["case_id"], "case_id": r["case_id"], "result": r["result"],
                "confidence": r["confidence"], "officer": r["officer"],
                "time": r["captured_at"].isoformat(), "location": r["location"] or "Field capture",
                "integrity": "verified", "storage": "postgresql",
                "sync_status": r["sync_status"],
            }
            for r in rows
        ]
    except Exception:
        return []


def get_case(case_id: str) -> dict[str, Any] | None:
    try:
        cid = _case_uuid(case_id)
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT c.case_reference AS case_id, c.classification AS result, c.confidence,
                       c.location, o.display_name AS officer, c.captured_at, c.model_version,
                       e.packet, e.image_sha256, e.payload_sha256, e.integrity_status
                FROM cases c
                JOIN operators o ON o.id=c.operator_id
                LEFT JOIN evidence e ON e.case_id=c.id
                WHERE c.id=%s OR c.case_reference=%s
                """,
                (cid, case_id),
            ).fetchone()
        if not row:
            return None
        packet = row["packet"] or {}
        stages = packet.get("stages", {})
        return {
            "id": row["case_id"], "case_id": row["case_id"], "result": row["result"],
            "confidence": row["confidence"], "officer": row["officer"],
            "time": row["captured_at"].isoformat(), "location": row["location"] or "Field capture",
            "integrity": row["integrity_status"] or "verified", "storage": "postgresql",
            "filename": stages.get("device_metadata", {}).get("filename"),
            "quality": stages.get("quality_gate", {}),
            "calibration": stages.get("calibration", {}),
            "deltae": stages.get("delta_e_classification", {}),
            "ml": stages.get("ml_confidence", {}),
            "resolved": packet.get("final_verdicts", {}),
            "model": stages.get("device_metadata", {}).get("model"),
            "evidence": {
                "image_sha256": row["image_sha256"],
                "payload_sha256": row["payload_sha256"],
                "integrity": row["integrity_status"] or "verified",
            },
            "evidence_packet": packet,
        }
    except Exception:
        return None


def get_evidence(case_id: str) -> dict[str, Any] | None:
    record = get_case(case_id)
    return record["evidence_packet"] if record else None


def get_summary() -> dict[str, Any] | None:
    try:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT count(*)::int AS total,
                       count(*) FILTER (WHERE classification='positive')::int AS positive,
                       count(*) FILTER (WHERE classification='negative')::int AS negative,
                       count(*) FILTER (WHERE classification='inconclusive')::int AS inconclusive
                FROM cases
                """
            ).fetchone()
        return {
            "total_cases": row["total"], "positive": row["positive"],
            "negative": row["negative"], "inconclusive": row["inconclusive"],
            "storage": "postgresql",
        }
    except Exception:
        return None


def database_available() -> bool:
    try:
        with _connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def _case_uuid(case_reference: str):
    return uuid.uuid5(uuid.NAMESPACE_URL, f"drug-companion:{case_reference}")


def _overall_ml(ml: dict) -> str | None:
    labels = [v.get("label") for v in ml.values() if v.get("model_available")]
    return max(set(labels), key=labels.count) if labels else None


def _max_ml_confidence(ml: dict) -> float | None:
    values = [float(v.get("confidence", 0.0)) for v in ml.values() if v.get("model_available")]
    return max(values) if values else None
