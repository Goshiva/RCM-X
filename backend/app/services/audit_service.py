from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from backend.app.core.config import AUDIT_LOG_FILE
from backend.app.models.audit_log import AuditLogRecord
from backend.app.repositories.audit_repository_sqlalchemy import AuditRepositorySQLAlchemy


class AuditService:
    """Captures immutable-style audit events for compliance and investigations."""

    def __init__(self, repository: Optional[Any] = None, log_path: Optional[str] = None) -> None:
        self.repository = repository or AuditRepositorySQLAlchemy()
        self.log_path = Path(log_path or AUDIT_LOG_FILE) if log_path or repository is None else None
        self._log_lock = Lock()

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
        actor_role: Optional[str] = None,
    ) -> AuditLogRecord:
        event_details = dict(details)
        if actor_role:
            event_details.setdefault("actor_role", actor_role)
        record = AuditLogRecord(
            action_type=action_type,
            entity_type=entity_type,
            details=event_details,
            user_id=user_id,
            chart_id=chart_id,
            entity_id=entity_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        record = self.repository.append(record)
        if self.log_path:
            event = {
                "audit_id": record.audit_id,
                "timestamp": record.created_at.isoformat() if record.created_at else None,
                "action_type": record.action_type,
                "entity_type": record.entity_type,
                "entity_id": record.entity_id,
                "chart_id": record.chart_id,
                "user_id": record.user_id,
                "actor_role": actor_role,
                "details": record.details,
            }
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_lock, self.log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(event, ensure_ascii=True, default=str) + "\n")
        return record
