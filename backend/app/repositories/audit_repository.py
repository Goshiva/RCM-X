from __future__ import annotations

from typing import Dict, List, Optional

from backend.app.models.audit_log import AuditLogRecord


class InMemoryAuditRepository:
    """Simple audit repository for structured event capture and retrieval."""

    def __init__(self) -> None:
        self._logs: Dict[int, AuditLogRecord] = {}
        self._next_id = 1

    def append(self, record: AuditLogRecord) -> AuditLogRecord:
        if record.audit_id is None:
            record.audit_id = self._next_id
            self._next_id += 1
        self._logs[record.audit_id] = record
        return record

    def list_for_chart(self, chart_id: int) -> List[AuditLogRecord]:
        return [entry for entry in self._logs.values() if entry.chart_id == chart_id]

    def list_for_user(self, user_id: int) -> List[AuditLogRecord]:
        return [entry for entry in self._logs.values() if entry.user_id == user_id]

    def get_all(self) -> List[AuditLogRecord]:
        return list(self._logs.values())
