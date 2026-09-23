from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DEFAULT_DATABASE_URL = "postgresql://drug_companion:drug_companion_dev@localhost:5432/drug_companion"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _connect():
    return psycopg.connect(database_url(), row_factory=dict_row)


def persist_case(record: dict[str, Any]) -> bool:
    """Persist a completed analysis. Returns False when PostgreSQL is unavailable."""
    try:
        case_uuid = _case_uuid(record["case_id"])
        model = record["model"]
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO operators(id, display_name)
                    VALUES (%s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
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
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, 'tflite', 'int8', %s, %s, %s,
                        %s, %s, %s, %s, FALSE, %s, %s
                    )
                    ON CONFLICT (model_name, model_version) DO UPDATE SET
                        artifact_sha256 = EXCLUDED.artifact_sha256,
                        metadata = EXCLUDED.metadata,
                        active = TRUE
                    """,
                    (
                        model["name"],
                        model["version"],
                        model["artifact_path"],
                        model["artifact_sha256"] or "0" * 64,
                        model["input"][0],
                        model["input"][1],
                        model["input"][2],
                        model["normalization"],
                        Jsonb(model["class_labels"]),
                        "bootstrap" if not model["target_validated"] else "target_validated",
                        model["target_validated"],
                        model["forensic_status"],
                        Jsonb(model),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO cases (
                        id, case_reference, operator_id, classification, confidence,
                        captured_at, model_version, app_version, sync_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'synced')
                    ON CONFLICT (id) DO UPDATE SET
                        classification = EXCLUDED.classification,
                        confidence = EXCLUDED.confidence
                    """,
                    (
                        case_uuid,
                        record["case_id"],
                        "demo-operator",
                        record["result"],
                        record["confidence"],
                        record["created_at"],
                        model["version"],
                        os.getenv("APP_VERSION", "0.3.0"),
                    ),
                )
                cur.execute(
                    """
                    SELECT id FROM model_registry
                    WHERE model_name = %s AND model_version = %s
                    """,
                    (model["name"], model["version"]),
                )
                model_row = cur.fetchone()
                model_id = model_row["id"] if model_row else None
                cur.execute(
                    """
                    INSERT INTO analysis_runs (
                        case_id, model_registry_id, pipeline_version, status,
                        final_classification, final_confidence, ml_classification,
                        ml_confidence, quality_gate, calibration, roi_extraction,
                        rule_engine, ml_inference, arbitration, completed_at
                    )
                    VALUES (
                        %s, %s, %s, 'completed', %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, now()
                    )
                    """,
                    (
                        case_uuid,
                        model_id,
                        os.getenv("PIPELINE_VERSION", "1.0.0"),
                        record["result"],
                        record["confidence"],
                        _overall_ml(record["ml"]),
                        _max_ml_confidence(record["ml"]),
                        Jsonb(record["quality"]),
                        Jsonb(record["calibration"]),
                        Jsonb({"detected": bool(record["deltae"])}),
                        Jsonb(record["deltae"]),
                        Jsonb(record["ml"]),
                        Jsonb(record["resolved"]),
                    ),
                )
                cur.execute(
                    "SELECT id FROM analysis_runs WHERE case_id = %s ORDER BY created_at DESC LIMIT 1",
                    (case_uuid,),
                )
                run_row = cur.fetchone()
                run_id = run_row["id"] if run_row else None
                cur.execute(
                    """
                    INSERT INTO evidence (
                        case_id, analysis_run_id, image_sha256, payload_sha256,
                        evidence_packet_sha256, image_size, schema_version,
                        integrity_status, packet
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'verified', %s)
                    ON CONFLICT (case_id) DO UPDATE SET
                        packet = EXCLUDED.packet,
                        payload_sha256 = EXCLUDED.payload_sha256
                    """,
                    (
                        case_uuid,
                        run_id,
                        record["evidence"]["image_sha256"],
                        record["evidence"]["payload_sha256"],
                        record["evidence"]["payload_sha256"],
                        None,
                        record["evidence_packet"]["schema_version"],
                        Jsonb(record["evidence_packet"]),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO audit_log(case_id, operator_id, action, details)
                    VALUES (%s, %s, 'analysis.completed', %s)
                    """,
                    (case_uuid, "demo-operator", Jsonb({"case_id": record["case_id"]})),
                )
        return True
    except Exception:
        return False


def _case_uuid(case_reference: str):
    import uuid
    return uuid.uuid5(uuid.NAMESPACE_URL, f"drug-companion:{case_reference}")


def _overall_ml(ml: dict) -> str | None:
    labels = [v.get("label") for v in ml.values() if v.get("model_available")]
    if not labels:
        return None
    return max(set(labels), key=labels.count)


def _max_ml_confidence(ml: dict) -> float | None:
    values = [float(v.get("confidence", 0.0)) for v in ml.values() if v.get("model_available")]
    return max(values) if values else None


def database_available() -> bool:
    try:
        with _connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
