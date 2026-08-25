from __future__ import annotations

from typing import Any

from backend.app.core.celery_app import celery_app
from backend.app.repositories.job_repository import InMemoryJobRepository, JobRecord
from backend.app.repositories.job_repository_sqlalchemy import JobRepositorySQLAlchemy
from backend.app.services.nlp_service import NLPService
from backend.app.services.workflow_services import audit_service, chart_repository, risk_service


chart_repo = chart_repository
job_repo = JobRepositorySQLAlchemy()
nlp = NLPService()
audit = audit_service


@celery_app.task(bind=True)
def process_chart_task(self: Any, chart_id: int) -> dict:
    task_id = str(self.request.id)
    job_repo.create(JobRecord(task_id=task_id, chart_id=chart_id, status='started'))

    chart = chart_repo.get_chart(chart_id)
    if not chart:
        job_repo.update_status(task_id, 'failed')
        return {'status': 'failed', 'reason': 'chart_not_found'}

    try:
        nlp_result = nlp.extract_pdf(chart.file_path)
        icd_codes = [
            entity['code']
            for entity in nlp_result.get('entities', [])
            if entity.get('type') == 'icd10'
        ]
        hcc_suggestions = nlp.suggest_hccs(icd_codes)

        risk.save_submission(
            chart_id=chart.chart_id,
            user_id=0,
            user_inputs={'nlp': nlp_result},
            captured_icd10_codes=icd_codes,
            mapped_hcc_versions=hcc_suggestions,
            calculated_raf_score=None,
        )

        audit.record_event(
            action_type='nlp_processed',
            entity_type='chart',
            details={'chart_id': chart.chart_id, 'icd_candidates': icd_codes},
            chart_id=chart.chart_id,
            user_id=0,
        )

        job_repo.update_status(task_id, 'completed')
        return {'status': 'completed', 'icd_candidates': icd_codes}

    except Exception as exc:
        job_repo.update_status(task_id, 'failed')
        return {'status': 'failed', 'reason': str(exc)}
