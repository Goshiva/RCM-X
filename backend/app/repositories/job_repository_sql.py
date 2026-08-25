from __future__ import annotations

import psycopg2
from typing import Optional, List

from backend.app.core.config import DATABASE_URL
from backend.app.repositories.job_repository import JobRecord


class JobRepositorySQL:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or DATABASE_URL
        if not self.dsn:
            raise ValueError("DATABASE_URL is required for JobRepositorySQL")

    def _get_conn(self):
        return psycopg2.connect(self.dsn)

    def create(self, job: JobRecord) -> JobRecord:
        sql = """
        INSERT INTO jobs (task_id, chart_id, status, created_at, updated_at)
        VALUES (%s, %s, %s, NOW(), NOW())
        ON CONFLICT (task_id) DO NOTHING
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (job.task_id, job.chart_id, job.status))
        return job

    def update_status(self, task_id: str, status: str) -> None:
        sql = """
        UPDATE jobs SET status = %s, updated_at = NOW() WHERE task_id = %s
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (status, task_id))

    def get(self, task_id: str) -> Optional[JobRecord]:
        sql = """
        SELECT task_id, chart_id, status FROM jobs WHERE task_id = %s
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (task_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return JobRecord(task_id=row[0], chart_id=row[1], status=row[2])

    def list_all(self) -> List[JobRecord]:
        sql = "SELECT task_id, chart_id, status FROM jobs ORDER BY created_at DESC"
        results: List[JobRecord] = []
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                for row in cur.fetchall():
                    results.append(JobRecord(task_id=row[0], chart_id=row[1], status=row[2]))
        return results
