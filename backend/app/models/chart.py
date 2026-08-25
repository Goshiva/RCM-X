from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ChartRecord:
    file_path: str
    original_filename: str
    status: str = "queued"
    priority: int = 0
    chart_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    locked_at: Optional[datetime] = None
    locked_until: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.uploaded_at = self.uploaded_at or now
        self.created_at = self.created_at or now
        self.updated_at = self.updated_at or now
