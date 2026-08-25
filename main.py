"""
HCC Medical Coding Tool - Command Line Interface
Advanced tool for insurance risk adjustment and HCC code prediction
"""

from src.ocr_module import extract_text_from_pdf
from src.nlp_identifier_v3 import extract_nlp_insights
from src.icd_mapper import ICD10Mapper
from src.ml_model import HCCPredictionModel
from src.risk_adjustment import RiskAdjustmentCalculator
from src.hcc_engine import detect_hierarchy_issues
from src.llm_integration import analyze_with_llm, generate_coding_summary, suggest_additional_codes, assess_audit_risk
import argparse
from pathlib import Path
import sys
import json

def analyze_medical_document(pdf_path: str, patient_data: dict = None):
    """
    Comprehensive medical document analysis pipeline
    
    Args:
        pdf_path: Path to medical PDF
        patient_data: Optional patient demographics (age, gender, insurance_model)
    """
    print("\n" + "="*80)
    print("HCC MEDICAL CODING ANALYSIS - v2.0")
    print("="*80)
    
    # Default patient data
    if patient_data is None:
        patient_data = {
            'age': 65,
            'gender': 'M',
            'insurance_model': 'MA',
            'patient_id': 'DEMO_001'
        }
    
    try:
        # Step 1: OCR
        print("\n[STEP 1] Extracting text from PDF...")
        ocr_text = extract_text_from_pdf(pdf_path)
        print(f"[OK] Extracted {len(ocr_text)} characters")
        
        # Step 2: NLP Analysis (Enhanced v3 with Biomedical NER)
        print("\n[STEP 2] Analyzing medical entities with Biomedical NLP...")
        nlp_results = extract_nlp_insights(ocr_text)
        print(f"[OK] Document type: {nlp_results['document_type']}")
        print(f"[OK] Confidence: {nlp_results.get('confidence', 0.7):.1%}")
        print(f"[OK] Extraction methods: {nlp_results['entities'].get('extraction_methods', ['regex'])}")
        
        # Step 3: Extract medical entities (v3 format)
        entities = nlp_results['entities'].get('entities', {})
        conditions = entities.get('conditions', [])
        medications = entities.get('medications', [])
        lab_values = entities.get('lab_values', [])
        vital_signs = entities.get('vital_signs', [])
        print(f"[OK] Found {len(conditions)} conditions")
        print(f"[OK] Found {len(medications)} medications")
        print(f"[OK] Found {len(lab_values)} lab values")
        print(f"[OK] Found {len(vital_signs)} vital signs")
        
        # Step 4: ML-based HCC prediction
        print("\n[STEP 3] Predicting HCC codes using ML model...")
        ml_model = HCCPredictionModel()
        # Convert v3 entities to format expected by ML model
        ml_entities = {
            'medical_conditions': [c.get('text') if isinstance(c, dict) else c for c in conditions],
            'medications': [m.get('text') if isinstance(m, dict) else m for m in medications],
        }
        predictions = ml_model.predict_hcc_codes(ml_entities)
        print(f"[OK] Generated {len(predictions)} HCC predictions")
        
        # Step 5: Map to ICD-10 codes
        print("\n[STEP 4] Mapping to ICD-10 codes...")
        icd_mapper = ICD10Mapper()
        icd_codes = []
        for prediction in predictions[:5]:  # Top 5
            for icd_code, hcc_map in icd_mapper.codes_db.items():
                if hcc_map.get('hcc') == prediction['hcc_code']:
                    icd_codes.append(icd_code)
                    break
        print(f"[OK] Identified {len(icd_codes)} ICD-10 codes")
        
        # Step 5b: Enhanced ICD-10 mapping from NLP entities (with ICD codes from regex)
        for condition in conditions:
            if isinstance(condition, dict) and condition.get('icd_code'):
                icd_codes.append(condition['icd_code'])
        icd_codes = list(set(icd_codes))  # Deduplicate
        print(f"[OK] Total ICD-10 codes after NLP mapping: {len(icd_codes)}")
        
        # Step 6: Calculate risk
        print("\n[STEP 5] Calculating risk adjustment factors...")
        calculator = RiskAdjustmentCalculator(patient_data['insurance_model'])
        report = calculator.generate_risk_report({
            'patient_id': patient_data.get('patient_id', 'UNKNOWN'),
            'icd10_codes': icd_codes,
            'demographics': {
                'age': patient_data['age'],
                'gender': patient_data['gender']
            }
        })
        print(f"[OK] RAF Score: {report['raf_calculation']['raf_score']:.3f}")
        print(f"[OK] Risk Level: {report['risk_level']}")
        print(f"[OK] Adjusted Premium: ${report['premium_calculation']['adjusted_premium']:,.2f}")
        
        # Step 7: AI-Enhanced Clinical Analysis (LLM Integration)
        print("\n[STEP 6] Running AI-enhanced clinical analysis...")
        hcc_codes = [m['hcc_name'] for m in report['raf_calculation']['hcc_mappings']]
        llm_analysis = analyze_with_llm(
            clinical_text=ocr_text,
            nlp_entities=nlp_results['entities'],
            analysis_type="hcc_analysis",
            patient_context=patient_data
        )
        print(f"[OK] LLM Analysis complete (model: {llm_analysis.get('_llm_metadata', {}).get('model', 'unknown')})")
        
        # Step 8: AI Code Suggestions
        print("\n[STEP 7] Generating AI code suggestions...")
        code_suggestions = suggest_additional_codes(
            clinical_text=ocr_text,
            current_icd10=icd_codes,
            current_hcc=hcc_codes,
            nlp_entities=nlp_results['entities']
        )
        print(f"[OK] Code suggestions generated")
        
        # Step 9: Audit Risk Assessment
        print("\n[STEP 8] Assessing audit risk...")
        audit_assessment = assess_audit_risk(
            clinical_text=ocr_text,
            coded_icd10=icd_codes,
            coded_hcc=hcc_codes,
            nlp_entities=nlp_results['entities']
        )
        print(f"[OK] Audit risk assessment complete")
        
        # Step 10: Display results
        print("\n" + "="*80)
        print("ANALYSIS RESULTS")
        print("="*80)
        
        print(f"\n[DOCUMENT INFORMATION]")
        print(f"  Document Type: {nlp_results['document_type']}")
        print(f"  Text Length: {nlp_results['text_length']} characters")
        print(f"  Word Count: {nlp_results['word_count']} words")
        print(f"  NLP Methods: {', '.join(nlp_results['entities'].get('extraction_methods', ['regex']))}")
        
        print(f"\n[PATIENT INFORMATION]")
        print(f"  Patient ID: {patient_data.get('patient_id', 'N/A')}")
        print(f"  Age: {patient_data['age']}")
        print(f"  Gender: {patient_data['gender']}")
        print(f"  Insurance Model: {patient_data['insurance_model']}")
        
        print(f"\n[IDENTIFIED MEDICAL CONDITIONS] ({len(conditions)})")
        for i, condition in enumerate(conditions[:10], 1):
            if isinstance(condition, dict):
                conf = condition.get('confidence', 0)
                icd = condition.get('icd_code', 'N/A')
                print(f"  {i}. {condition.get('text', 'Unknown')} (Confidence: {conf:.0%}, ICD: {icd})")
            else:
                print(f"  {i}. {condition}")
        
        print(f"\n[IDENTIFIED MEDICATIONS] ({len(medications)})")
        for i, med in enumerate(medications[:10], 1):
            if isinstance(med, dict):
                conf = med.get('confidence', 0)
                print(f"  {i}. {med.get('text', 'Unknown')} (Confidence: {conf:.0%})")
            else:
                print(f"  {i}. {med}")
        
        if lab_values:
            print(f"\n[LAB VALUES] ({len(lab_values)})")
            for i, lab in enumerate(lab_values[:10], 1):
                if isinstance(lab, dict):
                    meta = lab.get('metadata', {})
                    name = meta.get('lab_name', 'Unknown')
                    value = meta.get('value', 'N/A')
                    abnormal = meta.get('abnormal', False)
                    flag = " [ABNORMAL]" if abnormal else ""
                    print(f"  {i}. {name}: {value}{flag}")
                else:
                    print(f"  {i}. {lab}")
        
        if vital_signs:
            print(f"\n[VITAL SIGNS] ({len(vital_signs)})")
            for i, vital in enumerate(vital_signs[:10], 1):
                if isinstance(vital, dict):
                    vtype = vital.get('type', 'Unknown')
                    value = vital.get('value', 'N/A')
                    print(f"  {i}. {vtype}: {value}")
                else:
                    print(f"  {i}. {vital}")
        
        print(f"\n[HCC CODE PREDICTIONS] (Top 5)")
        for i, pred in enumerate(predictions[:5], 1):
            print(f"  {i}. {pred['hcc_code']} - Confidence: {pred['confidence']:.1%}")
            print(f"     Evidence: {pred['evidence']}")
        
        print(f"\n[ICD-10 CODES IDENTIFIED]")
        for i, code in enumerate(icd_codes[:10], 1):
            print(f"  {i}. {code} - {icd_mapper.get_icd10_description(code)}")
        
        print(f"\n[RISK ADJUSTMENT CALCULATION]")
        raf_calc = report['raf_calculation']
        print(f"  HCC Mappings: {len(raf_calc['hcc_mappings'])}")
        for mapping in raf_calc['hcc_mappings']:
            print(f"    - {mapping['icd10']}: {mapping['hcc_name']} (RAF: {mapping['raf_value']})")
        
        if raf_calc['hierarchy_issues']:
            print(f"\n  [WARNING] HIERARCHY ISSUES ({len(raf_calc['hierarchy_issues'])}):")
            for issue in raf_calc['hierarchy_issues']:
                print(f"    - {issue['message']}")
        
        print(f"\n[PREMIUM CALCULATION]")
        premium = report['premium_calculation']
        print(f"  Base Premium: ${premium['base_premium']:,.2f}")
        print(f"  Age Factor: {premium['age_factor']:.2f}x")
        print(f"  Gender Factor: {premium['gender_factor']:.2f}x")
        print(f"  RAF Multiplier: {premium['raf_multiplier']:.3f}x")
        print(f"  Adjusted Annual Premium: ${premium['adjusted_premium']:,.2f}")
        print(f"  Adjusted Monthly Premium: ${premium['monthly_premium']:,.2f}")
        
        print(f"\n[RISK ASSESSMENT]")
        print(f"  RAF Score: {raf_calc['raf_score']:.3f}")
        print(f"  Risk Level: {report['risk_level']}")
        
        # LLM Analysis Results
        print(f"\n[AI-ENHANCED ANALYSIS]")
        if 'conditions' in llm_analysis:
            print(f"  LLM Identified Conditions: {len(llm_analysis['conditions'])}")
            for c in llm_analysis['conditions'][:5]:
                print(f"    - {c.get('diagnosis', 'Unknown')}: {c.get('icd10', 'N/A')} (HCC: {c.get('hcc', 'N/A')})")
        if 'hierarchy_issues' in llm_analysis and llm_analysis['hierarchy_issues']:
            print(f"  LLM Hierarchy Issues: {len(llm_analysis['hierarchy_issues'])}")
            for issue in llm_analysis['hierarchy_issues'][:3]:
                print(f"    - {issue}")
        if 'documentation_gaps' in llm_analysis and llm_analysis['documentation_gaps']:
            print(f"  Documentation Gaps: {len(llm_analysis['documentation_gaps'])}")
            for gap in llm_analysis['documentation_gaps'][:3]:
                print(f"    - {gap}")
        if 'cdi_queries' in llm_analysis and llm_analysis['cdi_queries']:
            print(f"  CDI Queries: {len(llm_analysis['cdi_queries'])}")
            for q in llm_analysis['cdi_queries'][:3]:
                print(f"    - {q}")
        
        # AI Code Suggestions
        print(f"\n[AI CODE SUGGESTIONS]")
        if 'suggested_codes' in code_suggestions:
            for sugg in code_suggestions['suggested_codes'][:5]:
                print(f"  - {sugg.get('code', 'N/A')}: {sugg.get('description', 'N/A')} (Confidence: {sugg.get('confidence', 'N/A')})")
                print(f"    Rationale: {sugg.get('rationale', 'N/A')[:100]}...")
        
        # Audit Risk
        print(f"\n[AUDIT RISK ASSESSMENT]")
        if 'risk_level' in audit_assessment:
            print(f"  Risk Level: {audit_assessment['risk_level']}")
        if 'compliance_score' in audit_assessment:
            print(f"  Compliance Score: {audit_assessment['compliance_score']}/100")
        if 'vulnerabilities' in audit_assessment:
            for vuln in audit_assessment['vulnerabilities'][:3]:
                print(f"  - {vuln}")
        
        if report['recommendations']:
            print(f"\n[CODER RECOMMENDATIONS]")
            for i, rec in enumerate(report['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "="*80)
        print("Analysis Complete [OK]")
        print("="*80 + "\n")
        
        return report
        
    except Exception as e:
        print(f"\n[ERROR] Error: {str(e)}", file=sys.stderr)
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analyze a medical PDF for ICD/HCC candidates.')
    parser.add_argument('pdf_path', type=Path, help='Path to a medical PDF file')
    parser.add_argument('--patient-id', default='PAT_001')
    parser.add_argument('--age', type=int, default=65)
    parser.add_argument('--gender', choices=('M', 'F'), default='M')
    parser.add_argument('--insurance-model', default='MA')
    args = parser.parse_args()

    if not args.pdf_path.is_file():
        parser.error(f'PDF file not found: {args.pdf_path}')
    if args.pdf_path.suffix.lower() != '.pdf':
        parser.error('pdf_path must have a .pdf extension')

    analyze_medical_document(str(args.pdf_path), {
        'patient_id': args.patient_id,
        'age': args.age,
        'gender': args.gender,
        'insurance_model': args.insurance_model,
    })
