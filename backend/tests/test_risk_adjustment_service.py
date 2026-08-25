import unittest

from backend.app.repositories.risk_adjustment_repository import InMemoryRiskAdjustmentRepository
from backend.app.services.icd_validation_service import ICDValidationService
from backend.app.services.risk_adjustment_service import RiskAdjustmentService


class RiskAdjustmentServiceTests(unittest.TestCase):
    def test_icd_validation_accepts_common_codes(self) -> None:
        validator = ICDValidationService()

        self.assertTrue(validator.validate("E11.9"))
        self.assertTrue(validator.validate("I10"))
        self.assertFalse(validator.validate("invalid"))
        self.assertEqual(validator.suggest("E")[0], "E11.9")

    def test_save_submission_persists_risk_input(self) -> None:
        repo = InMemoryRiskAdjustmentRepository()
        service = RiskAdjustmentService(repository=repo)

        record = service.save_submission(
            chart_id=10,
            user_id=3,
            user_inputs={"notes": "reviewed"},
            captured_icd10_codes=["E11.9"],
            mapped_hcc_versions=[{"version": "V28", "hcc": "18"}],
            calculated_raf_score=1.25,
        )

        self.assertEqual(record.chart_id, 10)
        self.assertEqual(repo.get_latest_for_chart(10).calculated_raf_score, 1.25)


if __name__ == "__main__":
    unittest.main()
