import unittest

from backend.app.db_models import Chart, Base
from backend.app.core.db import engine
from backend.app.repositories.chart_repository_sqlalchemy import ChartRepositorySQLAlchemy


class ChartSQLAlchemyTests(unittest.TestCase):
    def setUp(self) -> None:
        # Recreate tables on in-memory test DB
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.repo = ChartRepositorySQLAlchemy()

    def test_create_and_get_chart(self) -> None:
        chart = Chart(file_path='/tmp/sql.pdf', original_filename='sql.pdf', priority=2)
        created = self.repo.create_chart(chart)
        fetched = self.repo.get_chart(created.chart_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.file_path, '/tmp/sql.pdf')


if __name__ == '__main__':
    unittest.main()
