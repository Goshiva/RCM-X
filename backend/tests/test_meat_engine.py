"""
Unit tests for Clinical Evidence and MEAT Criteria Engine
Tests section parsing, condition ontology binding, MEAT evaluation, negation detection, and NLPService integration.
"""

import unittest
from src.meat_engine import (
    meat_engine,
    ClinicalSectionParser,
    NegationDetector,
    SectionType,
    AuditGrade,
)
from backend.app.services.nlp_service import NLPService


SAMPLE_CLINICAL_NOTE = """
CHIEF COMPLAINT:
Follow-up for chronic conditions and routine exam.

HISTORY OF PRESENT ILLNESS:
Patient is a 68-year-old male with long-standing Type 2 Diabetes and Congestive Heart Failure.
Reports dyspnea on exertion has improved. No pedal edema noted recently.
Denies chest pain, palpitation, or acute distress.

PAST MEDICAL HISTORY:
1. Essential Hypertension
2. Chronic Obstructive Pulmonary Disease (COPD) - diagnosed 2018
3. Appendectomy (1995)

FAMILY HISTORY:
Mother had breast cancer. Father died of myocardial infarction.

CURRENT MEDICATIONS:
1. Metformin 1000 mg PO BID
2. Lantus Insulin 20 units SC at bedtime
3. Furosemide 40 mg PO daily
4. Lisinopril 20 mg PO daily
5. Atorvastatin 40 mg PO QHS

LABORATORY & DIAGNOSTIC DATA:
Recent labs reviewed:
HbA1c: 8.4% (elevated, poorly controlled)
eGFR: 42 mL/min/1.73m2 (consistent with CKD Stage 3b)
Serum Creatinine: 1.8 mg/dL
BNP: 180 pg/mL (improved from 450)
Echo from last month: Ejection Fraction 40%, mild left ventricular hypertrophy.

ASSESSMENT & PLAN:
1. Type 2 Diabetes Mellitus with hyperglycemia, uncontrolled.
   - Continue Metformin 1000 mg BID.
   - Titrate Lantus to 24 units nightly.
   - Recheck HbA1c in 3 months.
   - Counseled on low-glycemic diet and daily foot inspections.

2. Systolic Congestive Heart Failure (HFrEF), compensated.
   - Continue Furosemide 40 mg daily.
   - Continue Lisinopril 20 mg daily.
   - Daily weight tracking; call clinic if weight increases by >3 lbs in 2 days.

3. Chronic Kidney Disease, Stage 3b.
   - Monitor renal panel and eGFR every 3 months.
   - Avoid NSAIDs.
"""


class TestMEATEngine(unittest.TestCase):

    def setUp(self):
        self.engine = meat_engine

    def test_section_parser(self):
        sections = ClinicalSectionParser.parse_document(SAMPLE_CLINICAL_NOTE)
        section_types = [s.section_type for s in sections]

        self.assertIn(SectionType.HPI, section_types)
        self.assertIn(SectionType.PAST_MEDICAL_HISTORY, section_types)
        self.assertIn(SectionType.FAMILY_SOCIAL_HISTORY, section_types)
        self.assertIn(SectionType.MEDICATIONS, section_types)
        self.assertIn(SectionType.LABS_AND_DIAGNOSTICS, section_types)
        self.assertIn(SectionType.ASSESSMENT_AND_PLAN, section_types)

        # Verify audit weights
        ap_section = next(s for s in sections if s.section_type == SectionType.ASSESSMENT_AND_PLAN)
        self.assertEqual(ap_section.audit_weight, "HIGH")

        pmh_section = next(s for s in sections if s.section_type == SectionType.PAST_MEDICAL_HISTORY)
        self.assertEqual(pmh_section.audit_weight, "LOW")

    def test_negation_detector(self):
        # Negated cases
        self.assertTrue(NegationDetector.is_negated("Denies chest pain or shortness of breath", "chest pain"))
        self.assertTrue(NegationDetector.is_negated("Chest x-ray shows no evidence of heart failure", "heart failure"))
        self.assertTrue(NegationDetector.is_negated("DVT was ruled out by Doppler", "DVT"))

        # Non-negated cases
        self.assertFalse(NegationDetector.is_negated("Patient diagnosed with Type 2 Diabetes", "diabetes"))
        self.assertFalse(NegationDetector.is_negated("Assessment: Heart failure with reduced ejection fraction", "heart failure"))

        # Family history cases
        self.assertTrue(NegationDetector.is_family_history("Mother had breast cancer", SectionType.GENERAL))
        self.assertTrue(NegationDetector.is_family_history("Father with stroke", SectionType.FAMILY_SOCIAL_HISTORY))
        self.assertFalse(NegationDetector.is_family_history("Patient has history of stroke", SectionType.HPI))

    def test_diabetes_meat_evaluation(self):
        sections = ClinicalSectionParser.parse_document(SAMPLE_CLINICAL_NOTE)
        analysis = self.engine.evaluate_condition("diabetes", sections)

        self.assertEqual(analysis.canonical_condition, "Type 2 Diabetes Mellitus")
        self.assertEqual(analysis.audit_grade, AuditGrade.AUDIT_PROOF)
        self.assertFalse(analysis.is_pmh_only)
        self.assertFalse(analysis.is_negated)

        # Check that individual MEAT criteria are satisfied
        criteria = analysis.criteria
        self.assertTrue(criteria["T"]["present"], "Treat should be present (Metformin / Insulin)")
        self.assertTrue(criteria["E"]["present"], "Evaluate should be present (HbA1c reviewed)")
        self.assertTrue(criteria["A"]["present"], "Assess should be present (Assessment & Plan)")
        self.assertTrue(criteria["M"]["present"], "Monitor should be present (Recheck in 3 months / foot exam)")
        self.assertGreaterEqual(analysis.meat_score, 3)

    def test_heart_failure_meat_evaluation(self):
        sections = ClinicalSectionParser.parse_document(SAMPLE_CLINICAL_NOTE)
        analysis = self.engine.evaluate_condition("heart failure", sections)

        self.assertEqual(analysis.canonical_condition, "Congestive Heart Failure")
        self.assertEqual(analysis.audit_grade, AuditGrade.AUDIT_PROOF)
        self.assertTrue(analysis.criteria["T"]["present"], "Treat should be satisfied by Furosemide")
        self.assertTrue(analysis.criteria["E"]["present"], "Evaluate should be satisfied by BNP / Echo")
        self.assertTrue(analysis.criteria["A"]["present"], "Assess should be satisfied in A/P")
        self.assertTrue(analysis.criteria["M"]["present"], "Monitor should be satisfied by daily weight / DOE")

    def test_copd_pmh_only_at_risk(self):
        """COPD is listed in PMH, but not mentioned or treated in A/P in this note."""
        sections = ClinicalSectionParser.parse_document(SAMPLE_CLINICAL_NOTE)
        analysis = self.engine.evaluate_condition("copd", sections)

        # COPD has no active medications (no albuterol/spiriva in meds) and no A/P mention
        self.assertEqual(analysis.audit_grade, AuditGrade.PMH_ONLY_AT_RISK)
        self.assertEqual(analysis.meat_score, 0)
        self.assertTrue(analysis.is_pmh_only)

    def test_document_analysis_and_query_opportunities(self):
        doc_result = self.engine.analyze_document(SAMPLE_CLINICAL_NOTE)

        self.assertIn("audit_summary", doc_result)
        summary = doc_result["audit_summary"]
        self.assertGreaterEqual(summary["audit_proof_count"], 2)  # Diabetes & CHF
        self.assertGreaterEqual(summary["at_risk_count"], 1)      # COPD

    def test_nlp_service_integration(self):
        service = NLPService()
        result = service.analyze_text(SAMPLE_CLINICAL_NOTE)

        self.assertIn("audit_summary", result)
        self.assertIn("entities", result)

        # Find condition entities
        condition_entities = [e for e in result["entities"] if e.get("type") == "condition"]
        self.assertGreater(len(condition_entities), 0)

        # Check that MEAT fields exist on condition entities
        for entity in condition_entities:
            self.assertIn("meat_criteria", entity)
            self.assertIn("meat_score", entity)
            self.assertIn("audit_grade", entity)
            self.assertIn("audit_grade_label", entity)
            self.assertIn("meat_evidence", entity)


if __name__ == "__main__":
    unittest.main()
