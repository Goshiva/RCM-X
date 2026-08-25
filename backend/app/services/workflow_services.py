"""Shared workflow service instances for the Flask process."""

from backend.app.core.config import CHARTS_FILE
from backend.app.repositories.chart_repository import JsonChartRepository
from backend.app.services.audit_service import AuditService
from backend.app.services.chart_assignment_service import ChartAssignmentService
from backend.app.services.icd_validation_service import ICDValidationService
from backend.app.services.risk_adjustment_service import RiskAdjustmentService
from backend.app.workers.nlp_worker import InMemoryNLPWorker

chart_repository = JsonChartRepository(CHARTS_FILE)
chart_assignment_service = ChartAssignmentService(repository=chart_repository)
nlp_worker = InMemoryNLPWorker(repository=chart_repository)
risk_service = RiskAdjustmentService()
audit_service = AuditService()
icd_validator = ICDValidationService()
