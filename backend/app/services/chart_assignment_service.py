from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Optional

from backend.app.models.chart import ChartRecord
from backend.app.repositories.chart_repository import InMemoryChartRepository


class ChartAssignmentError(Exception):
    """Raised when a chart assignment or release action is invalid."""


class ChartAssignmentService:
    """Coordinates chart claiming, locking, release, and reassignment for coders and admins.

    For the future PostgreSQL-backed implementation, use the following pattern to preserve
    transactional isolation:
        SELECT chart_id FROM charts WHERE status = 'queued' ORDER BY priority DESC, uploaded_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED;
    """

    def __init__(self, repository: Optional[InMemoryChartRepository] = None, lock_duration_minutes: int = 60) -> None:
        self.repository = repository or InMemoryChartRepository()
        self.lock_duration_minutes = lock_duration_minutes
        self._lock = RLock()

    def claim_next_available_chart(self, user_id: int, actor_role: str = "coder") -> Optional[ChartRecord]:
        if actor_role not in {"coder", "admin", "master_admin"}:
            raise ChartAssignmentError("Unsupported role")

        with self._lock:
            now = datetime.now(timezone.utc)
            existing = [
                chart for chart in self.repository.list_charts()
                if chart.assigned_to_user_id == user_id
                and chart.status in {"locked", "in_progress"}
                and (not chart.locked_until or chart.locked_until > now)
            ]
            if existing:
                existing.sort(key=lambda item: item.chart_id)
                return existing[0]

            candidates = [
                chart for chart in self.repository.list_charts()
                if chart.status in {"queued", "released"}
                or (chart.status == "locked" and chart.locked_until and chart.locked_until <= now)
            ]
            if not candidates:
                return None

            candidates.sort(key=lambda item: (-item.priority, item.uploaded_at, item.chart_id))
            selected = candidates[0]
            selected.status = "locked"
            selected.assigned_to_user_id = user_id
            selected.locked_at = now
            selected.locked_until = now + timedelta(minutes=self.lock_duration_minutes)
            return self.repository.update_chart(selected)

    def release_chart(self, chart_id: int, actor_user_id: int, actor_role: str = "coder") -> bool:
        with self._lock:
            chart = self.repository.get_chart(chart_id)
            if not chart:
                return False

            if actor_role not in {"admin", "master_admin"} and chart.assigned_to_user_id != actor_user_id:
                raise ChartAssignmentError("Only the assigned user or a master admin can release a chart")

            chart.status = "released"
            chart.assigned_to_user_id = None
            chart.locked_at = None
            chart.locked_until = None
            self.repository.update_chart(chart)
            return True

    def reassign_chart(self, chart_id: int, new_user_id: int, actor_user_id: int, actor_role: str = "coder") -> bool:
        if actor_role not in {"admin", "master_admin"}:
            raise ChartAssignmentError("Only master admins can reassign charts")

        with self._lock:
            chart = self.repository.get_chart(chart_id)
            if not chart:
                return False

            chart.assigned_to_user_id = new_user_id
            chart.status = "locked"
            chart.locked_at = datetime.now(timezone.utc)
            chart.locked_until = chart.locked_at + timedelta(minutes=self.lock_duration_minutes)
            self.repository.update_chart(chart)
            return True
