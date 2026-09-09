from __future__ import annotations

from collections import Counter
from typing import Any

from backend.app.services.audit_service import AuditService


class CodingLearningService:
    """Builds explainable coding feedback signals from completed L2 audits.

    This is a feedback store, not an autonomous clinical decision-maker. Signals
    are surfaced as suggestions for human review and never silently change codes.
    """

    def __init__(self, audit: AuditService) -> None:
        self.audit = audit

    def record_audit_feedback(self, *, chart_id: int, user_id: int, quality: dict[str, Any]) -> None:
        for code in quality.get("missed_codes", []):
            self.audit.record_event(
                action_type="learning_signal_recorded",
                entity_type="coding_feedback",
                details={"signal": "missed_code", "code": code, "source": "l2_audit"},
                user_id=user_id,
                chart_id=chart_id,
            )
        for code in quality.get("wrong_codes", []):
            self.audit.record_event(
                action_type="learning_signal_recorded",
                entity_type="coding_feedback",
                details={"signal": "wrong_code", "code": code, "source": "l2_audit"},
                user_id=user_id,
                chart_id=chart_id,
            )
        for code in quality.get("added_codes", []):
            self.audit.record_event(
                action_type="learning_signal_recorded",
                entity_type="coding_feedback",
                details={"signal": "confirmed_addition", "code": code, "source": "l2_audit"},
                user_id=user_id,
                chart_id=chart_id,
            )

    def learned_signals(self) -> dict[str, list[dict[str, Any]]]:
        missed: Counter[str] = Counter()
        wrong: Counter[str] = Counter()
        added: Counter[str] = Counter()
        for event in self.audit.repository.get_all():
            if event.action_type != "learning_signal_recorded":
                continue
            code = str(event.details.get("code", "")).upper()
            if not code:
                continue
            signal = event.details.get("signal")
            if signal == "missed_code":
                missed[code] += 1
            elif signal == "wrong_code":
                wrong[code] += 1
            elif signal == "confirmed_addition":
                added[code] += 1

        def ranked(values: Counter[str]) -> list[dict[str, Any]]:
            return [{"code": code, "count": count} for code, count in values.most_common(20)]

        return {"missed_codes": ranked(missed), "wrong_codes": ranked(wrong), "confirmed_additions": ranked(added)}
