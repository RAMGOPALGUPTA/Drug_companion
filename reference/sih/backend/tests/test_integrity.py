from datetime import datetime, timezone
import unittest
from uuid import UUID

from app.main import CaseIn, canonical, digest


class IntegrityTests(unittest.TestCase):
    def sample_case(self) -> CaseIn:
        return CaseIn(
            id=UUID("c38fbb69-4451-4b13-bd9d-29671460a908"),
            operator_id="demo-operator",
            classification="inconclusive",
            confidence=0.0,
            latitude=28.6139,
            longitude=77.209,
            captured_at=datetime(2026, 9, 10, 10, 30, tzinfo=timezone.utc),
            model_version="pending-labelled-training-data",
            app_version="1.1.0",
            image_sha256="A" * 64,
        )

    def test_digest_is_stable_and_normalizes_image_hash(self) -> None:
        case = self.sample_case()
        self.assertEqual(case.image_sha256, "a" * 64)
        self.assertEqual(digest(case), digest(case))
        self.assertIn('"image_sha256":"' + "a" * 64, canonical(case))

    def test_digest_changes_when_a_record_field_changes(self) -> None:
        original = self.sample_case()
        changed = original.model_copy(update={"confidence": 0.5})
        self.assertNotEqual(digest(original), digest(changed))


if __name__ == "__main__":
    unittest.main()
