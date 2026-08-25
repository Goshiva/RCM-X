import unittest

from backend.app.models.audit_log import AuditLogRecord
from backend.app.models.risk_adjustment_input import RiskAdjustmentInputRecord
from backend.app.repositories.audit_repository_sqlalchemy import AuditRepositorySQLAlchemy
from backend.app.repositories.job_repository_sqlalchemy import JobRepositorySQLAlchemy
from backend.app.repositories.job_repository import JobRecord
from backend.app.repositories.risk_adjustment_repository_sqlalchemy import RiskAdjustmentRepositorySQLAlchemy


class SQLAlchemyRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audit_repo = AuditRepositorySQLAlchemy()
        self.risk_repo = RiskAdjustmentRepositorySQLAlchemy()
        self.job_repo = JobRepositorySQLAlchemy()

    def test_audit_repository_persists_and_lists(self) -> None:
        record = self.audit_repo.append(
            AuditLogRecord(
                action_type="chart_claimed",
                entity_type="chart",
                details={"chart_id": 12},
                user_id=4,
                chart_id=12,
            )
        )

        self.assertIsNotNone(record.audit_id)
        self.assertEqual(self.audit_repo.list_for_chart(12)[0].audit_id, record.audit_id)

    def test_risk_repository_persists_and_fetches_latest(self) -> None:
        created = self.risk_repo.create(
            RiskAdjustmentInputRecord(
                chart_id=99,
                user_id=5,
                user_inputs={"notes": "reviewed"},
                captured_icd10_codes=["E11.9"],
                mapped_hcc_versions=[{"version": "V28", "hcc": "18"}],
                calculated_raf_score=1.25,
            )
        )

        self.assertIsNotNone(created.input_id)
        latest = self.risk_repo.get_latest_for_chart(99)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.input_id, created.input_id)

    def test_job_repository_persists_and_updates_status(self) -> None:
        created = self.job_repo.create(JobRecord(task_id="task-123", chart_id=88, status="pending"))

        self.assertEqual(created.task_id, "task-123")
        self.job_repo.update_status("task-123", "completed")
        stored = self.job_repo.get("task-123")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.status, "completed")


if __name__ == "__main__":
    unittest.main()
