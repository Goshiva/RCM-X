import unittest
import time

from backend.app.repositories.chart_repository import InMemoryChartRepository
from backend.app.models.chart import ChartRecord
from backend.app.workers.nlp_worker import InMemoryNLPWorker


class NLPWorkerTests(unittest.TestCase):
    def test_enqueue_and_process_next(self) -> None:
        repo = InMemoryChartRepository()
        chart = repo.create_chart(ChartRecord(file_path="/tmp/test.pdf", original_filename="test.pdf", priority=1))
        worker = InMemoryNLPWorker(repository=repo)
        worker.enqueue(chart.chart_id)
        worker.process_next()

        # After processing, an initial risk input should exist
        latest = worker.risk.get_latest_for_chart(chart.chart_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.chart_id, chart.chart_id)


if __name__ == "__main__":
    unittest.main()
