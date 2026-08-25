from __future__ import annotations

from typing import Dict, List, Optional

from backend.app.models.risk_adjustment_input import RiskAdjustmentInputRecord


class InMemoryRiskAdjustmentRepository:
    """Stores coder submissions and calculated RAF results for a chart."""

    def __init__(self) -> None:
        self._records: Dict[int, RiskAdjustmentInputRecord] = {}
        self._next_id = 1

    def create(self, record: RiskAdjustmentInputRecord) -> RiskAdjustmentInputRecord:
        if record.input_id is None:
            record.input_id = self._next_id
            self._next_id += 1
        self._records[record.input_id] = record
        return record

    def get_by_chart(self, chart_id: int) -> List[RiskAdjustmentInputRecord]:
        return [entry for entry in self._records.values() if entry.chart_id == chart_id]

    def get_latest_for_chart(self, chart_id: int) -> Optional[RiskAdjustmentInputRecord]:
        chart_records = [entry for entry in self._records.values() if entry.chart_id == chart_id]
        return max(chart_records, key=lambda item: item.created_at, default=None) if chart_records else None

    def update(self, record: RiskAdjustmentInputRecord) -> RiskAdjustmentInputRecord:
        if record.input_id is not None:
            self._records[record.input_id] = record
        return record
