"""
Tamper-evident evidence packet generation.

Produces a JSON evidence record for a single test-strip analysis,
including a chained SHA-256 hash over every stage's output so any
post-hoc modification of the record is detectable. Optionally embeds
the source image bytes (base64) for a fully self-contained packet.
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
    """Deterministic JSON serialization so hashing is reproducible."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


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
    """
    Assemble the full evidence packet. Each stage's output is hashed
    individually, and those hashes are chained (hash-of-hashes) into a
    single top-level chained_hash so tampering with any single stage's
    record, or their order, invalidates the chain.
    """
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

    final_verdicts = resolved_calls

    # Chain: hash each stage in a fixed order, then hash the concatenation.
    stage_order = ["quality_gate", "calibration", "roi_extraction",
                    "delta_e_classification", "ml_confidence", "device_metadata"]
    stage_hashes = []
    for name in stage_order:
        stage_json = _canonical_json({name: stages[name]})
        stage_hashes.append(_sha256_hex(stage_json.encode("utf-8")))

    chain_input = source_hash + "".join(stage_hashes) + _canonical_json(final_verdicts)
    chained_hash = _sha256_hex(chain_input.encode("utf-8"))

    source_b64 = base64.b64encode(source_image_bytes).decode("ascii") if cfg.embed_source_image else None

    return EvidencePacket(
        packet_id=packet_id,
        schema_version=cfg.schema_version,
        created_utc=created,
        source_image_sha256=source_hash,
        stages=stages,
        final_verdicts=final_verdicts,
        chained_hash=chained_hash,
        source_image_b64=source_b64,
    )


def save_packet(packet: EvidencePacket, cfg: EvidenceConfig) -> str:
    """Write the packet to <output_dir>/<packet_id>.json and return the path."""
    os.makedirs(cfg.output_dir, exist_ok=True)
    path = os.path.join(cfg.output_dir, f"{packet.packet_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(packet.to_dict(), f, indent=2, sort_keys=True, default=str)
    return path


def verify_packet(packet_path: str) -> Dict[str, Any]:
    """
    Re-derive the chained hash from a saved packet's contents and confirm
    it matches the stored chained_hash. Returns a verification report.
    """
    with open(packet_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stage_order = ["quality_gate", "calibration", "roi_extraction",
                    "delta_e_classification", "ml_confidence", "device_metadata"]
    stages = data.get("stages", {})
    stage_hashes = []
    for name in stage_order:
        stage_json = _canonical_json({name: stages.get(name, {})})
        stage_hashes.append(_sha256_hex(stage_json.encode("utf-8")))

    chain_input = data["source_image_sha256"] + "".join(stage_hashes) + _canonical_json(data["final_verdicts"])
    recomputed = _sha256_hex(chain_input.encode("utf-8"))

    valid = recomputed == data["chained_hash"]

    image_hash_valid = None
    if data.get("source_image_b64"):
        raw = base64.b64decode(data["source_image_b64"])
        image_hash_valid = _sha256_hex(raw) == data["source_image_sha256"]

    return {
        "packet_id": data.get("packet_id"),
        "chain_valid": valid,
        "recomputed_hash": recomputed,
        "stored_hash": data["chained_hash"],
        "source_image_hash_valid": image_hash_valid,
    }
