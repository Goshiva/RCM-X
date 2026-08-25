from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RiskAdjustmentInputRecord:
    chart_id: int
    user_id: int
    user_inputs: Dict[str, Any] = field(default_factory=dict)
    captured_icd10_codes: List[str] = field(default_factory=list)
    mapped_hcc_versions: List[Dict[str, Any]] = field(default_factory=list)
    calculated_raf_score: Optional[float] = None
    input_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.created_at = self.created_at or now
        self.updated_at = self.updated_at or now
