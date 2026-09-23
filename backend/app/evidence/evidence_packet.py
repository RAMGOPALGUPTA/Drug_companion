"""
Tamper-evident evidence packet generation and verification.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import base64
import hashlib
import json
import os
import uuid

from app.inference.config import EvidenceConfig


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


_STAGE_ORDER = [
    "quality_gate", "calibration", "roi_extraction",
    "delta_e_classification", "ml_confidence", "device_metadata",
]


@dataclass
class EvidencePacket:
    packet_id: str
    schema_version: str
    created_utc: str
    source_image_sha256: str
    stages: Dict[str, Any]
    final_verdicts: Dict[str, Any]
    chained_hash: str
    source_image_b64: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def build_evidence_packet(
    source_image_bytes: bytes,
    quality_report: dict,
    calibration_result: dict,
    roi_summary: dict,
    deltae_verdicts: Dict[str, dict],
    ml_verdicts: Dict[str, dict],
    resolved_calls: Dict[str, dict],
    device_metadata: Optional[dict],
    cfg: EvidenceConfig,
) -> EvidencePacket:
    packet_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()
    source_hash = _sha256_hex(source_image_bytes)
    stages = {
        "quality_gate": quality_report,
        "calibration": calibration_result,
        "roi_extraction": roi_summary,
        "delta_e_classification": deltae_verdicts,
        "ml_confidence": ml_verdicts,
        "device_metadata": device_metadata or {},
    }
    stage_hashes = [
        _sha256_hex(_canonical_json({name: stages[name]}).encode("utf-8"))
        for name in _STAGE_ORDER
    ]
    chained_hash = _sha256_hex(
        (source_hash + "".join(stage_hashes) + _canonical_json(resolved_calls)).encode("utf-8")
    )
    source_b64 = (
        base64.b64encode(source_image_bytes).decode("ascii")
        if cfg.embed_source_image else None
    )
    return EvidencePacket(
        packet_id=packet_id, schema_version=cfg.schema_version, created_utc=created,
        source_image_sha256=source_hash, stages=stages, final_verdicts=resolved_calls,
        chained_hash=chained_hash, source_image_b64=source_b64,
    )


def verify_packet_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    stages = data.get("stages", {})
    stage_hashes = [
        _sha256_hex(_canonical_json({name: stages.get(name, {})}).encode("utf-8"))
        for name in _STAGE_ORDER
    ]
    recomputed = _sha256_hex(
        (data["source_image_sha256"] + "".join(stage_hashes) +
         _canonical_json(data["final_verdicts"])).encode("utf-8")
    )
    image_hash_valid = None
    if data.get("source_image_b64"):
        try:
            raw = base64.b64decode(data["source_image_b64"], validate=True)
            image_hash_valid = _sha256_hex(raw) == data["source_image_sha256"]
        except Exception:
            image_hash_valid = False
    return {
        "packet_id": data.get("packet_id"),
        "chain_valid": recomputed == data.get("chained_hash"),
        "recomputed_hash": recomputed,
        "stored_hash": data.get("chained_hash"),
        "source_image_hash_valid": image_hash_valid,
        "schema_version": data.get("schema_version"),
    }


def save_packet(packet: EvidencePacket, cfg: EvidenceConfig) -> str:
    os.makedirs(cfg.output_dir, exist_ok=True)
    path = os.path.join(cfg.output_dir, f"{packet.packet_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(packet.to_dict(), f, indent=2, sort_keys=True, default=str)
    return path


def verify_packet(packet_path: str) -> Dict[str, Any]:
    with open(packet_path, "r", encoding="utf-8") as f:
        return verify_packet_dict(json.load(f))
