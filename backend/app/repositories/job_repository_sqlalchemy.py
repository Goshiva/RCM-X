from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.db import SessionLocal, engine
from backend.app.db_models import Base, Job
from backend.app.repositories.job_repository import JobRecord

Base.metadata.create_all(bind=engine)


class JobRepositorySQLAlchemy:
    def __init__(self) -> None:
        Base.metadata.create_all(bind=engine)

    def create(self, job: JobRecord) -> JobRecord:
        session: Session = SessionLocal()
        try:
            model = Job(
                task_id=job.task_id,
                chart_id=job.chart_id,
                status=job.status,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return job
        finally:
            session.close()

    def update_status(self, task_id: str, status: str) -> None:
        session: Session = SessionLocal()
        try:
            model = session.get(Job, task_id)
            if model is None:
                return
            model.status = status
            model.updated_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()

    def get(self, task_id: str) -> Optional[JobRecord]:
        session: Session = SessionLocal()
        try:
            model = session.get(Job, task_id)
            if model is None:
                return None
            return self._to_record(model)
        finally:
            session.close()

    def list_all(self) -> List[JobRecord]:
        session: Session = SessionLocal()
        try:
            stmt = select(Job).order_by(Job.created_at.desc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_record(row) for row in rows]
        finally:
            session.close()

    @staticmethod
    def _to_record(model: Job) -> JobRecord:
        return JobRecord(
            task_id=model.task_id,
            chart_id=model.chart_id,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
