from __future__ import annotations

import threading
import time
from typing import List, Optional

from backend.app.services.nlp_service import NLPService
from backend.app.repositories.chart_repository import InMemoryChartRepository
from backend.app.services.audit_service import AuditService
from backend.app.services.risk_adjustment_service import RiskAdjustmentService


class InMemoryNLPWorker:
    """A simple in-memory queue worker for processing charts.

    This is a prototype. Replace with an async broker (Celery/RQ) for production.
    """

    def __init__(self, repository: Optional[InMemoryChartRepository] = None) -> None:
        self.queue: List[int] = []
        self.repo = repository or InMemoryChartRepository()
        self.nlp = NLPService()
        self.audit = AuditService()
        self.risk = RiskAdjustmentService()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def enqueue(self, chart_id: int) -> None:
        if chart_id not in self.queue:
            self.queue.append(chart_id)

    def process_next(self) -> None:
        if not self.queue:
            return
        chart_id = self.queue.pop(0)
        chart = self.repo.get_chart(chart_id)
        if not chart:
            return

        chart.status = "in_progress"
        self.repo.update_chart(chart)

        try:
            nlp_result = self.nlp.extract_pdf(chart.file_path)
            icd_codes = [
                entity["code"]
                for entity in nlp_result.get("entities", [])
                if entity.get("type") == "icd10"
            ]
            hcc_suggestions = self.nlp.suggest_hccs(icd_codes)

            self.risk.save_submission(
                chart_id=chart.chart_id,
                user_id=0,
                user_inputs={"nlp_result": nlp_result},
                captured_icd10_codes=icd_codes,
                mapped_hcc_versions=hcc_suggestions,
                calculated_raf_score=None,
            )

            self.audit.record_event(
                action_type="nlp_processed",
                entity_type="chart",
                details={"chart_id": chart.chart_id, "icd_candidates": icd_codes},
                chart_id=chart.chart_id,
                user_id=0,
            )

            chart.status = "queued"
        except Exception as exc:
            chart.status = "failed"
            self.audit.record_event(
                action_type="nlp_processing_failed",
                entity_type="chart",
                details={"chart_id": chart.chart_id, "error": str(exc)},
                chart_id=chart.chart_id,
                user_id=0,
            )
        self.repo.update_chart(chart)

    def run(self, poll_interval: float = 1.0) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def _loop():
            while not self._stop.is_set():
                try:
                    self.process_next()
                except Exception:
                    pass
                time.sleep(poll_interval)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
