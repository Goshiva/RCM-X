from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.db import SessionLocal, engine
from backend.app.db_models import AuditLog, Base
from backend.app.models.audit_log import AuditLogRecord

Base.metadata.create_all(bind=engine)


class AuditRepositorySQLAlchemy:
    def __init__(self) -> None:
        Base.metadata.create_all(bind=engine)

    def append(self, record: AuditLogRecord) -> AuditLogRecord:
        session: Session = SessionLocal()
        try:
            model = AuditLog(
                user_id=record.user_id,
                chart_id=record.chart_id,
                action_type=record.action_type,
                entity_type=record.entity_type,
                entity_id=record.entity_id,
                details=record.details,
                ip_address=record.ip_address,
                user_agent=record.user_agent,
                created_at=record.created_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            record.audit_id = model.audit_id
            record.created_at = model.created_at
            return record
        finally:
            session.close()

    def list_for_chart(self, chart_id: int) -> List[AuditLogRecord]:
        session: Session = SessionLocal()
        try:
            stmt = select(AuditLog).where(AuditLog.chart_id == chart_id).order_by(AuditLog.created_at.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_record(row) for row in rows]
        finally:
            session.close()

    def list_for_user(self, user_id: int) -> List[AuditLogRecord]:
        session: Session = SessionLocal()
        try:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.created_at.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_record(row) for row in rows]
        finally:
            session.close()

    def get_all(self) -> List[AuditLogRecord]:
        session: Session = SessionLocal()
        try:
            stmt = select(AuditLog).order_by(AuditLog.created_at.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_record(row) for row in rows]
        finally:
            session.close()

    @staticmethod
    def _to_record(model: AuditLog) -> AuditLogRecord:
        return AuditLogRecord(
            action_type=model.action_type,
            entity_type=model.entity_type,
            details=model.details or {},
            user_id=model.user_id,
            chart_id=model.chart_id,
            entity_id=model.entity_id,
            ip_address=model.ip_address,
            user_agent=model.user_agent,
            audit_id=model.audit_id,
            created_at=model.created_at,
        )
