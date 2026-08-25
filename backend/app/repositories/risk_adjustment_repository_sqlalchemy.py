from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.db import SessionLocal, engine
from backend.app.db_models import Base, RiskAdjustmentInput
from backend.app.models.risk_adjustment_input import RiskAdjustmentInputRecord

Base.metadata.create_all(bind=engine)


class RiskAdjustmentRepositorySQLAlchemy:
    def __init__(self) -> None:
        Base.metadata.create_all(bind=engine)

    def create(self, record: RiskAdjustmentInputRecord) -> RiskAdjustmentInputRecord:
        session: Session = SessionLocal()
        try:
            model = RiskAdjustmentInput(
                chart_id=record.chart_id,
                user_id=record.user_id,
                user_inputs=record.user_inputs,
                captured_icd10_codes=record.captured_icd10_codes,
                mapped_hcc_versions=record.mapped_hcc_versions,
                calculated_raf_score=record.calculated_raf_score,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            record.input_id = model.input_id
            record.created_at = model.created_at
            record.updated_at = model.updated_at
            return record
        finally:
            session.close()

    def get_by_id(self, input_id: int) -> Optional[RiskAdjustmentInputRecord]:
        session: Session = SessionLocal()
        try:
            row = session.get(RiskAdjustmentInput, input_id)
            return self._to_record(row) if row else None
        finally:
            session.close()

    def get_all(self) -> List[RiskAdjustmentInputRecord]:
        session: Session = SessionLocal()
        try:
            stmt = select(RiskAdjustmentInput).order_by(RiskAdjustmentInput.created_at.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_record(row) for row in rows]
        finally:
            session.close()

    def get_by_chart(self, chart_id: int) -> List[RiskAdjustmentInputRecord]:
        session: Session = SessionLocal()
        try:
            stmt = select(RiskAdjustmentInput).where(RiskAdjustmentInput.chart_id == chart_id).order_by(RiskAdjustmentInput.created_at.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._to_record(row) for row in rows]
        finally:
            session.close()

    def get_latest_for_chart(self, chart_id: int) -> Optional[RiskAdjustmentInputRecord]:
        session: Session = SessionLocal()
        try:
            stmt = (
                select(RiskAdjustmentInput)
                .where(RiskAdjustmentInput.chart_id == chart_id)
                .order_by(RiskAdjustmentInput.created_at.desc())
                .limit(1)
            )
            row = session.execute(stmt).scalars().first()
            return self._to_record(row) if row else None
        finally:
            session.close()

    def update(self, record: RiskAdjustmentInputRecord) -> RiskAdjustmentInputRecord:
        session: Session = SessionLocal()
        try:
            model = session.get(RiskAdjustmentInput, record.input_id)
            if not model:
                raise ValueError(f"Risk adjustment input {record.input_id} not found")
            model.user_inputs = record.user_inputs
            model.captured_icd10_codes = record.captured_icd10_codes
            model.mapped_hcc_versions = record.mapped_hcc_versions
            model.calculated_raf_score = record.calculated_raf_score
            model.updated_at = record.updated_at
            session.commit()
            session.refresh(model)
            record.updated_at = model.updated_at
            return record
        finally:
            session.close()

    @staticmethod
    def _to_record(model: RiskAdjustmentInput) -> RiskAdjustmentInputRecord:
        return RiskAdjustmentInputRecord(
            chart_id=model.chart_id,
            user_id=model.user_id,
            user_inputs=model.user_inputs or {},
            captured_icd10_codes=model.captured_icd10_codes or [],
            mapped_hcc_versions=model.mapped_hcc_versions or [],
            calculated_raf_score=float(model.calculated_raf_score) if model.calculated_raf_score is not None else None,
            input_id=model.input_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
