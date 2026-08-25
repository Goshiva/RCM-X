from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class AuditLogRecord:
    action_type: str
    entity_type: str
    details: Dict[str, Any]
    user_id: Optional[int] = None
    chart_id: Optional[int] = None
    entity_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    audit_id: Optional[int] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.created_at = self.created_at or datetime.now(timezone.utc)
