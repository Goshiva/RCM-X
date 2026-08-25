from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.app.models.risk_adjustment_input import RiskAdjustmentInputRecord
from backend.app.repositories.risk_adjustment_repository_sqlalchemy import RiskAdjustmentRepositorySQLAlchemy


class RiskAdjustmentService:
    """Captures coder decisions and calculated RAF values for a chart."""

    def __init__(self, repository: Optional[Any] = None) -> None:
        self.repository = repository or RiskAdjustmentRepositorySQLAlchemy()

    def save_submission(
        self,
        *,
        chart_id: int,
        user_id: int,
        user_inputs: Dict[str, Any],
        captured_icd10_codes: List[str],
        mapped_hcc_versions: List[Dict[str, Any]],
        calculated_raf_score: Optional[float] = None,
    ) -> RiskAdjustmentInputRecord:
        record = RiskAdjustmentInputRecord(
            chart_id=chart_id,
            user_id=user_id,
            user_inputs=user_inputs,
            captured_icd10_codes=captured_icd10_codes,
            mapped_hcc_versions=mapped_hcc_versions,
            calculated_raf_score=calculated_raf_score,
        )
        return self.repository.create(record)

    def update_submission(
        self,
        *,
        input_id: int,
        user_inputs: Optional[Dict[str, Any]] = None,
        captured_icd10_codes: Optional[List[str]] = None,
        mapped_hcc_versions: Optional[List[Dict[str, Any]]] = None,
        calculated_raf_score: Optional[float] = None,
    ) -> Optional[RiskAdjustmentInputRecord]:
        existing = None
        if hasattr(self.repository, "_records"):
            for entry in self.repository._records.values():
                if entry.input_id == input_id:
                    existing = entry
                    break
        elif hasattr(self.repository, "get_all"):
            for entry in self.repository.get_all():
                if entry.input_id == input_id:
                    existing = entry
                    break
        elif hasattr(self.repository, "get_by_id"):
            existing = self.repository.get_by_id(input_id)

        if not existing:
            return None

        if user_inputs is not None:
            existing.user_inputs = user_inputs
        if captured_icd10_codes is not None:
            existing.captured_icd10_codes = captured_icd10_codes
        if mapped_hcc_versions is not None:
            existing.mapped_hcc_versions = mapped_hcc_versions
        if calculated_raf_score is not None:
            existing.calculated_raf_score = calculated_raf_score

        return self.repository.update(existing)

    def get_latest_for_chart(self, chart_id: int) -> Optional[RiskAdjustmentInputRecord]:
        return self.repository.get_latest_for_chart(chart_id)
