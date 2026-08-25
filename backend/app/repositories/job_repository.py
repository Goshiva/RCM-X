from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class JobRecord:
    task_id: str
    chart_id: int
    status: str = 'pending'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.created_at = self.created_at or now
        self.updated_at = self.updated_at or now


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}

    def create(self, job: JobRecord) -> JobRecord:
        self._jobs[job.task_id] = job
        return job

    def update_status(self, task_id: str, status: str) -> None:
        job = self._jobs.get(task_id)
        if job:
            job.status = status
            job.updated_at = datetime.now(timezone.utc)

    def get(self, task_id: str) -> Optional[JobRecord]:
        return self._jobs.get(task_id)

    def list_all(self):
        return list(self._jobs.values())
