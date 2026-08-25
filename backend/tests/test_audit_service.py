import unittest

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


if __name__ == "__main__":
    unittest.main()
