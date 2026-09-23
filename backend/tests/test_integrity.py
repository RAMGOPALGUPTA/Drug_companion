import unittest

from app.evidence.evidence_packet import build_evidence_packet, verify_packet_dict
from app.inference.config import EvidenceConfig


class IntegrityTests(unittest.TestCase):
    def sample_packet(self) -> dict:
        packet = build_evidence_packet(
            b"synthetic-test-image",
            {"passed": True},
            {"passed": True},
            {"strip_found": True},
            {"opioid": {"call": "inconclusive"}},
            {"opioid": {"label": "negative", "confidence": 0.8, "model_available": True}},
            {"opioid": {"final_call": "negative"}},
            {"filename": "fixture.jpg"},
            EvidenceConfig(embed_source_image=True),
        )
        return packet.to_dict()

    def test_packet_chain_is_valid(self) -> None:
        result = verify_packet_dict(self.sample_packet())
        self.assertTrue(result["chain_valid"])
        self.assertTrue(result["source_image_hash_valid"])

    def test_packet_chain_detects_tampering(self) -> None:
        packet = self.sample_packet()
        packet["final_verdicts"]["opioid"]["final_call"] = "positive"
        result = verify_packet_dict(packet)
        self.assertFalse(result["chain_valid"])


if __name__ == "__main__":
    unittest.main()
