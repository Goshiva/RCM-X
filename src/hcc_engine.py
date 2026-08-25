# CMS 2025 HCC Mapping Database
# Maps ICD-10-CM codes to HCC categories and RAF scores
# Medicare Advantage Risk Adjustment Program

HCC_MAPPINGS = {
    # Infectious and Parasitic Diseases (HCC 1-6)
    "HCC001": {"name": "HIV/AIDS", "icd10_codes": ["B20", "B21", "B22"], "raf_score": 0.193, "category": "Infectious"},
    "HCC002": {"name": "Septicemia, Meningitis", "icd10_codes": ["A40", "A41", "G00", "G03"], "raf_score": 0.229, "category": "Infectious"},
    "HCC006": {"name": "Tuberculosis", "icd10_codes": ["A15", "A16", "A17", "A18"], "raf_score": 0.158, "category": "Infectious"},
    
    # Neoplasms (HCC 8-34)
    "HCC008": {"name": "Metastatic Cancer", "icd10_codes": ["C80", "C34", "C80.1"], "raf_score": 0.317, "category": "Neoplasm"},
    "HCC010": {"name": "Lung Cancer", "icd10_codes": ["C34"], "raf_score": 0.205, "category": "Neoplasm"},
    "HCC011": {"name": "Breast Cancer", "icd10_codes": ["C50"], "raf_score": 0.175, "category": "Neoplasm"},
    "HCC012": {"name": "Colorectal Cancer", "icd10_codes": ["C18", "C19", "C20"], "raf_score": 0.175, "category": "Neoplasm"},
    "HCC017": {"name": "Acute Leukemia", "icd10_codes": ["C91", "C92", "C93", "C94", "C95"], "raf_score": 0.275, "category": "Neoplasm"},
    
    # Endocrine (HCC 35-40)
    "HCC035": {"name": "Diabetes without complications", "icd10_codes": ["E10.9", "E11.9", "E13.9"], "raf_score": 0.124, "category": "Endocrine"},
    "HCC036": {"name": "Diabetes with complications", "icd10_codes": ["E10.65", "E11.65", "E10.21", "E11.21"], "raf_score": 0.159, "category": "Endocrine"},
    "HCC037": {"name": "Thyroid Disorder", "icd10_codes": ["E01", "E02", "E06"], "raf_score": 0.009, "category": "Endocrine"},
    
    # Circulatory System (HCC 46-86)
    "HCC046": {"name": "Acute Myocardial Infarction", "icd10_codes": ["I21"], "raf_score": 0.220, "category": "Circulatory"},
    "HCC047": {"name": "Heart Failure", "icd10_codes": ["I50"], "raf_score": 0.301, "category": "Circulatory"},
    "HCC048": {"name": "Chronic Obstructive Pulmonary Disease", "icd10_codes": ["J41", "J42", "J43", "J44"], "raf_score": 0.107, "category": "Respiratory"},
    "HCC051": {"name": "Cerebrovascular Disease", "icd10_codes": ["I63", "I64", "I65", "I66"], "raf_score": 0.103, "category": "Circulatory"},
    "HCC052": {"name": "Peripheral Vascular Disease", "icd10_codes": ["I73", "I74"], "raf_score": 0.102, "category": "Circulatory"},
    "HCC053": {"name": "Hypertension", "icd10_codes": ["I10", "I11", "I12"], "raf_score": 0.011, "category": "Circulatory"},
    
    # Respiratory (HCC 111-113)
    "HCC111": {"name": "Chronic Respiratory Conditions", "icd10_codes": ["J44"], "raf_score": 0.107, "category": "Respiratory"},
    "HCC112": {"name": "Cystic Fibrosis", "icd10_codes": ["E84"], "raf_score": 0.433, "category": "Respiratory"},
    "HCC113": {"name": "Lung Disease", "icd10_codes": ["J84", "J70"], "raf_score": 0.105, "category": "Respiratory"},
    
    # Kidney Disease (HCC 134-135)
    "HCC134": {"name": "Chronic Kidney Disease Stage 5", "icd10_codes": ["N18.5"], "raf_score": 0.413, "category": "Renal"},
    "HCC135": {"name": "Chronic Kidney Disease Stages 3-4", "icd10_codes": ["N18.3", "N18.4"], "raf_score": 0.183, "category": "Renal"},
    
    # Psychiatric (HCC 157-158)
    "HCC157": {"name": "Schizophrenia", "icd10_codes": ["F20"], "raf_score": 0.137, "category": "Psychiatric"},
    "HCC158": {"name": "Major Depression", "icd10_codes": ["F32", "F33"], "raf_score": 0.098, "category": "Psychiatric"},
    
    # Musculoskeletal (HCC 164)
    "HCC164": {"name": "Rheumatoid Arthritis", "icd10_codes": ["M05", "M06"], "raf_score": 0.099, "category": "Musculoskeletal"},
    
    # Neurological (HCC 159-163)
    "HCC159": {"name": "Dementia", "icd10_codes": ["G30", "F01"], "raf_score": 0.118, "category": "Neurological"},
    "HCC160": {"name": "Multiple Sclerosis", "icd10_codes": ["G35"], "raf_score": 0.111, "category": "Neurological"},
    "HCC161": {"name": "Seizure", "icd10_codes": ["G40"], "raf_score": 0.108, "category": "Neurological"},
}

# HCC Hierarchy - codes that supersede lower-value codes
HCC_HIERARCHY = {
    "HCC001": [],  # HIV is top level
    "HCC002": [],  # Septicemia is top level
    "HCC008": ["HCC010", "HCC011", "HCC012"],  # Metastatic cancer supersedes specific cancers
    "HCC010": [],  # Lung cancer
    "HCC047": ["HCC046"],  # Heart failure supersedes MI
}

def get_hcc_from_icd10(icd10_code: str) -> dict:
    """
    Get HCC category from ICD-10 code
    
    Args:
        icd10_code: ICD-10 diagnosis code
    
    Returns:
        HCC mapping dictionary or None
    """
    icd10_code = icd10_code.strip().upper()
    
    for hcc_id, hcc_data in HCC_MAPPINGS.items():
        # Check exact match and partial match
        for code in hcc_data["icd10_codes"]:
            if icd10_code == code or icd10_code.startswith(code):
                return {"hcc_id": hcc_id, **hcc_data}
    
    return None


def get_raf_score(hcc_list: list, demographics: dict = None) -> float:
    """
    Calculate RAF score from HCC codes
    
    Args:
        hcc_list: List of HCC codes
        demographics: Patient demographics (age, gender)
    
    Returns:
        RAF score
    """
    raf_score = 0.0
    
    # Base RAF by age
    if demographics and demographics.get("age"):
        age = demographics["age"]
        if age < 34:
            raf_score += 0.0
        elif age < 44:
            raf_score += 0.055
        elif age < 54:
            raf_score += 0.119
        elif age < 64:
            raf_score += 0.214
        elif age < 74:
            raf_score += 0.321
        elif age < 84:
            raf_score += 0.461
        else:
            raf_score += 0.610
    
    # Add HCC scores
    for hcc_id in hcc_list:
        if hcc_id in HCC_MAPPINGS:
            raf_score += HCC_MAPPINGS[hcc_id]["raf_score"]
    
    return round(raf_score, 3)


def detect_hierarchy_issues(hcc_list: list) -> list:
    """
    Detect conflicting/redundant HCCs in the hierarchy
    
    Args:
        hcc_list: List of HCC codes
    
    Returns:
        List of hierarchy conflicts
    """
    issues = []
    for hcc_id in hcc_list:
        if hcc_id in HCC_HIERARCHY:
            supersedes = HCC_HIERARCHY[hcc_id]
            for superseded in supersedes:
                if superseded in hcc_list:
                    issues.append({
                        "type": "hierarchy_conflict",
                        "primary": hcc_id,
                        "superseded": superseded,
                        "primary_name": HCC_MAPPINGS.get(hcc_id, {}).get("name", "Unknown"),
                        "superseded_name": HCC_MAPPINGS.get(superseded, {}).get("name", "Unknown"),
                        "message": f"{hcc_id} ({HCC_MAPPINGS.get(hcc_id, {}).get('name')}) supersedes {superseded} - recommend removing {superseded}",
                        "action": f"Remove {superseded} and keep {hcc_id}"
                    })
    return issues


def get_category_summary(hcc_list: list) -> dict:
    """Get summary of HCC categories"""
    categories = {}
    for hcc_id in hcc_list:
        if hcc_id in HCC_MAPPINGS:
            category = HCC_MAPPINGS[hcc_id]["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append(hcc_id)
    return categories
