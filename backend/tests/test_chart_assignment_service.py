import unittest

from backend.app.models.chart import ChartRecord
from backend.app.repositories.chart_repository import InMemoryChartRepository
from backend.app.services.chart_assignment_service import ChartAssignmentService


class ChartAssignmentServiceTests(unittest.TestCase):
    def test_claim_next_available_chart_prevents_double_claim(self) -> None:
        repo = InMemoryChartRepository()
        repo.create_chart(ChartRecord(file_path="/tmp/a.pdf", original_filename="a.pdf", priority=5))

        service = ChartAssignmentService(repository=repo)
        first = service.claim_next_available_chart(user_id=1, actor_role="coder")
        second = service.claim_next_available_chart(user_id=2, actor_role="coder")

        self.assertEqual(first.chart_id, 1)
        self.assertIsNone(second)
        self.assertEqual(first.status, "locked")
        self.assertEqual(first.assigned_to_user_id, 1)

    def test_admin_can_release_locked_chart(self) -> None:
        repo = InMemoryChartRepository()
        repo.create_chart(ChartRecord(file_path="/tmp/c.pdf", original_filename="c.pdf", priority=1))

        service = ChartAssignmentService(repository=repo)
        claimed = service.claim_next_available_chart(user_id=1, actor_role="coder")
        released = service.release_chart(claimed.chart_id, actor_user_id=1, actor_role="master_admin")

        self.assertTrue(released)
        self.assertEqual(repo.get_chart(claimed.chart_id).status, "released")


if __name__ == "__main__":
    unittest.main()
