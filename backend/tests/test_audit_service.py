import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.models.audit_log import AuditLogRecord
from backend.app.repositories.audit_repository import InMemoryAuditRepository
from backend.app.services.audit_service import AuditService


class AuditServiceTests(unittest.TestCase):
    def test_record_event_persists_to_repository(self) -> None:
        repo = InMemoryAuditRepository()
        service = AuditService(repository=repo)

        entry = service.record_event(
            action_type="chart_claimed",
            entity_type="chart",
            details={"chart_id": 1},
            user_id=7,
            chart_id=1,
        )

        self.assertEqual(entry.action_type, "chart_claimed")
        self.assertEqual(repo.get_all()[0].chart_id, 1)

    def test_record_event_writes_jsonl_activity_log(self) -> None:
        repo = InMemoryAuditRepository()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "activity.jsonl"
            service = AuditService(repository=repo, log_path=str(path))
            entry = service.record_event(
                action_type="code_added",
                entity_type="chart",
                details={"code": "E11.9"},
                user_id=7,
                chart_id=1,
                actor_role="coder_l1",
            )
            line = path.read_text(encoding="utf-8").strip()
            self.assertIn('"action_type": "code_added"', line)
            self.assertIn('"actor_role": "coder_l1"', line)
            self.assertEqual(entry.details["actor_role"], "coder_l1")


if __name__ == "__main__":
    unittest.main()
