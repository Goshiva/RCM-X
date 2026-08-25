from __future__ import annotations

from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.core.db import SessionLocal, engine
from backend.app.db_models import Base, Chart


# Ensure tables exist for local/in-memory DBs during tests
Base.metadata.create_all(bind=engine)


class ChartRepositorySQLAlchemy:
    def __init__(self) -> None:
        pass

    def create_chart(self, chart_obj) -> Chart:
        session: Session = SessionLocal()
        try:
            session.add(chart_obj)
            session.commit()
            session.refresh(chart_obj)
            return chart_obj
        finally:
            session.close()

    def get_chart(self, chart_id: int) -> Optional[Chart]:
        session: Session = SessionLocal()
        try:
            stmt = select(Chart).where(Chart.chart_id == chart_id)
            res = session.execute(stmt).scalars().first()
            return res
        finally:
            session.close()

    def list_charts(self) -> List[Chart]:
        session: Session = SessionLocal()
        try:
            stmt = select(Chart)
            res = session.execute(stmt).scalars().all()
            return res
        finally:
            session.close()

    def update_chart(self, chart_obj: Chart) -> Chart:
        session: Session = SessionLocal()
        try:
            session.merge(chart_obj)
            session.commit()
            session.refresh(chart_obj)
            return chart_obj
        finally:
            session.close()
