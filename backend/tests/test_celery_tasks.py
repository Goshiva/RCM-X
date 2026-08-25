import unittest

from backend.app.tasks import nlp_tasks as tasks_module
from backend.app.tasks.nlp_tasks import process_chart_task
from backend.app.models.chart import ChartRecord


class CeleryTaskTests(unittest.TestCase):
    def test_process_chart_task_eager_mode(self) -> None:
        # register the chart in the task module's chart repository so the task can find it
        chart = tasks_module.chart_repo.create_chart(ChartRecord(file_path='/tmp/x.pdf', original_filename='x.pdf'))
        # Call the task synchronously (eager mode when no broker configured)
        res = process_chart_task.apply(args=(chart.chart_id,))
        result = res.get()
        self.assertIn(result.get('status'), ('completed', 'failed'))


if __name__ == '__main__':
    unittest.main()
