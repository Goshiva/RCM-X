"""
Validation Test Suite for HCC Medical Coding Tool
Tests all major components for functionality
"""

import sys
from datetime import datetime

def test_imports():
    """Test all module imports"""
    print("\n[TEST 1] Testing Module Imports...")
    try:
        from src.ocr_module import extract_text_from_pdf
        from src.nlp_identifier_v3 import extract_nlp_insights
        from src.icd_mapper import ICD10Mapper
        from src.ml_model import HCCPredictionModel
        from src.hcc_engine import get_hcc_from_icd10, get_raf_score
        from src.risk_adjustment import RiskAdjustmentCalculator
        from src.audit_logger import AuditLogger
        from src.report_generator import ReportGenerator
        print("[OK] All modules imported successfully")
        return True
    except Exception as e:
        print(f"[FAIL] Import error: {e}")
        return False


def test_icd_mapper():
    """Test ICD-10 mapper functionality"""
    print("\n[TEST 2] Testing ICD-10 Mapper...")
    try:
        from src.icd_mapper import ICD10Mapper
        
        mapper = ICD10Mapper()
        
        # Test validation
        valid, msg = mapper.validate_icd10_code("I50")
        assert valid, f"I50 should be valid: {msg}"
        print("[OK] ICD-10 validation works")
        
        # Test HCC lookup
        hcc = mapper.get_hcc_from_icd10("I50")
        assert hcc == "HCC047", f"I50 should map to HCC047, got {hcc}"
        print("[OK] ICD-10 to HCC mapping works")
        
        # Test condition search
        codes = mapper.find_icd10_by_condition("heart failure")
        assert len(codes) > 0, "Should find codes for heart failure"
        print(f"[OK] Condition search works (found {len(codes)} codes)")
        
        return True
    except Exception as e:
        print(f"[FAIL] ICD mapper error: {e}")
        return False


def test_ml_model():
    """Test ML prediction model"""
    print("\n[TEST 3] Testing ML Prediction Model...")
    try:
        from src.ml_model import HCCPredictionModel
        
        model = HCCPredictionModel()
        
        # Test with sample data
        entities = {
            'medical_conditions': ['heart failure', 'diabetes type 2'],
            'medications': ['lisinopril', 'metformin'],
            'lab_values': {'HbA1c': '8.2'}
        }
        
        predictions = model.predict_hcc_codes(entities)
        assert len(predictions) > 0, "Should generate predictions"
        print(f"[OK] ML model generated {len(predictions)} predictions")
        
        # Check confidence scores
        for pred in predictions:
            assert 0 <= pred['confidence'] <= 1, f"Invalid confidence: {pred['confidence']}"
        print("[OK] Confidence scores valid")
        
        return True
    except Exception as e:
        print(f"[FAIL] ML model error: {e}")
        return False


def test_hcc_engine():
    """Test HCC engine functionality"""
    print("\n[TEST 4] Testing HCC Engine...")
    try:
        from src.hcc_engine import get_hcc_from_icd10, get_raf_score, detect_hierarchy_issues
        
        # Test HCC lookup
        hcc_info = get_hcc_from_icd10("I50")
        assert hcc_info is not None, "I50 should map to HCC"
        print(f"[OK] HCC lookup works (found {hcc_info['hcc_id']})")
        
        # Test RAF calculation
        hcc_list = ["HCC047", "HCC035"]
        demographics = {"age": 65, "gender": "M"}
        raf = get_raf_score(hcc_list, demographics)
        assert raf > 0, "RAF should be positive"
        print(f"[OK] RAF calculation works (score: {raf:.3f})")
        
        # Test hierarchy detection
        issues = detect_hierarchy_issues(["HCC008", "HCC010"])  # Conflict
        assert len(issues) > 0, "Should detect hierarchy conflict"
        print(f"[OK] Hierarchy detection works (found {len(issues)} issues)")
        
        return True
    except Exception as e:
        print(f"[FAIL] HCC engine error: {e}")
        return False


def test_risk_calculator():
    """Test risk adjustment calculator"""
    print("\n[TEST 5] Testing Risk Calculator...")
    try:
        from src.risk_adjustment import RiskAdjustmentCalculator
        
        calc = RiskAdjustmentCalculator("MA")
        
        report = calc.generate_risk_report({
            'patient_id': 'TEST_001',
            'icd10_codes': ['I50', 'E11.9'],
            'demographics': {'age': 65, 'gender': 'M'}
        })
        
        assert report['raf_calculation']['raf_score'] > 0, "RAF score should be positive"
        print(f"[OK] Risk calculation works (RAF: {report['raf_calculation']['raf_score']:.3f})")
        
        assert report['premium_calculation']['adjusted_premium'] > 0, "Premium should be positive"
        print(f"[OK] Premium calculation works (${report['premium_calculation']['adjusted_premium']:,.2f})")
        
        assert report['risk_level'] in ['Low Risk', 'Moderate Risk', 'High Risk', 'Very High Risk']
        print(f"[OK] Risk classification works (Level: {report['risk_level']})")
        
        return True
    except Exception as e:
        print(f"[FAIL] Risk calculator error: {e}")
        return False


def test_nlp_extraction():
    """Test NLP entity extraction"""
    print("\n[TEST 6] Testing NLP Extraction...")
    try:
        from src.nlp_identifier_v3 import extract_nlp_insights
        
        sample_text = """
        Patient: John Smith
        DOB: 01/15/1959
        Diagnosis: Type 2 Diabetes Mellitus, Hypertension, Heart Failure
        Medications: Metformin, Lisinopril, Metoprolol
        Lab Results: HbA1c 7.8, BP 145/92, Glucose 180
        """
        
        results = extract_nlp_insights(sample_text)
        
        ents = results['entities'].get('entities', {})
        conditions = ents.get('conditions', [])
        medications = ents.get('medications', [])
        
        assert len(conditions) > 0, "Should extract conditions"
        print(f"[OK] Condition extraction works (found {len(conditions)})")
        
        assert len(medications) > 0, "Should extract medications"
        print(f"[OK] Medication extraction works (found {len(medications)})")
        
        assert results['document_type'] in ['prescription', 'medical_record', 'office_visit', 'progress_note', 'consultation', 'lab_report', 'imaging_report', 'operative_report', 'discharge_summary']
        print(f"[OK] Document type classification works")
        
        # Check extraction methods
        methods = results['entities'].get('extraction_methods', [])
        print(f"[OK] Extraction methods: {methods}")
        
        return True
    except Exception as e:
        print(f"[FAIL] NLP extraction error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_audit_logger():
    """Test audit logging"""
    print("\n[TEST 7] Testing Audit Logger...")
    try:
        from src.audit_logger import AuditLogger
        
        logger = AuditLogger()
        
        # Test logging
        logger.log_calculation({
            'patient_id': 'TEST_001',
            'insurance_model': 'MA',
            'icd10_codes': ['I50', 'E11.9'],
            'raf_score': 0.450,
            'adjusted_premium': 15000,
            'risk_level': 'High Risk'
        })
        print("[OK] Calculation logging works")
        
        # Test retrieval
        trail = logger.get_patient_audit_trail('TEST_001')
        assert len(trail) > 0, "Should retrieve audit trail"
        print(f"[OK] Audit trail retrieval works (found {len(trail)} events)")
        
        return True
    except Exception as e:
        print(f"[FAIL] Audit logger error: {e}")
        return False


def run_all_tests():
    """Run all validation tests"""
    print("="*70)
    print("HCC MEDICAL CODING TOOL - VALIDATION TEST SUITE")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        test_imports,
        test_icd_mapper,
        test_ml_model,
        test_hcc_engine,
        test_risk_calculator,
        test_nlp_extraction,
        test_audit_logger,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"[FAIL] Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n[OK] ALL TESTS PASSED - Tool is ready for production!")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} test(s) failed - Please fix issues before deployment")
        return 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
