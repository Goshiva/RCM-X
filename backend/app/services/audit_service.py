from __future__ import annotations

from typing import Any, Optional

from backend.app.models.audit_log import AuditLogRecord
from backend.app.repositories.audit_repository_sqlalchemy import AuditRepositorySQLAlchemy


class AuditService:
    """Captures immutable-style audit events for compliance and investigations."""

    def __init__(self, repository: Optional[Any] = None) -> None:
        self.repository = repository or AuditRepositorySQLAlchemy()

    def record_event(
        self,
        *,
        action_type: str,
        entity_type: str,
        details: dict,
        user_id: Optional[int] = None,
        chart_id: Optional[int] = None,
        entity_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLogRecord:
        record = AuditLogRecord(
            action_type=action_type,
            entity_type=entity_type,
            details=details,
            user_id=user_id,
            chart_id=chart_id,
            entity_id=entity_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return self.repository.append(record)
