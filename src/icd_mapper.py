"""
ICD-10-CM Code Mapper and Validator
Maps diagnoses to ICD-10-CM codes and validates code format
"""

from typing import Dict, List, Tuple
import re

# ICD-10-CM code validation patterns
ICD10_PATTERN = r'^[A-Z]\d{2}(?:\.\d{1,2})?$'

# Common ICD-10-CM codes database
ICD10_CODES_DB = {
    # Infectious Diseases
    "B20": {"description": "Human immunodeficiency virus [HIV] disease", "hcc": "HCC001"},
    "A40": {"description": "Streptococcal sepsis", "hcc": "HCC002"},
    "A41": {"description": "Other sepsis", "hcc": "HCC002"},
    "G00": {"description": "Bacterial meningitis", "hcc": "HCC002"},
    "A15": {"description": "Respiratory tuberculosis", "hcc": "HCC006"},
    
    # Malignant Neoplasms
    "C80": {"description": "Malignant neoplasm, unspecified", "hcc": "HCC008"},
    "C34": {"description": "Malignant neoplasm of unspecified part of unspecified bronchus or lung", "hcc": "HCC010"},
    "C50": {"description": "Malignant neoplasm of breast", "hcc": "HCC011"},
    "C18": {"description": "Malignant neoplasm of colon", "hcc": "HCC012"},
    "C19": {"description": "Malignant neoplasm of rectosigmoid junction", "hcc": "HCC012"},
    "C20": {"description": "Malignant neoplasm of rectum", "hcc": "HCC012"},
    "C91": {"description": "Lymphoid leukemia", "hcc": "HCC017"},
    "C92": {"description": "Myeloid leukemia", "hcc": "HCC017"},
    "C93": {"description": "Monocytic leukemia", "hcc": "HCC017"},
    
    # Endocrine Diseases
    "E10.9": {"description": "Type 1 diabetes mellitus without complications", "hcc": "HCC035"},
    "E11.9": {"description": "Type 2 diabetes mellitus without complications", "hcc": "HCC035"},
    "E13.9": {"description": "Other specified diabetes mellitus without complications", "hcc": "HCC035"},
    "E10.65": {"description": "Type 1 diabetes with hyperglycemia", "hcc": "HCC036"},
    "E11.65": {"description": "Type 2 diabetes with hyperglycemia", "hcc": "HCC036"},
    "E01": {"description": "Iodine-deficiency-related thyroid disorders and allied conditions", "hcc": "HCC037"},
    "E02": {"description": "Nontoxic goiter", "hcc": "HCC037"},
    "E06": {"description": "Thyroiditis", "hcc": "HCC037"},
    
    # Circulatory System Diseases
    "I21": {"description": "ST elevation (STEMI) and non-ST elevation (NSTEMI) myocardial infarction", "hcc": "HCC046"},
    "I50": {"description": "Heart failure", "hcc": "HCC047"},
    "J41": {"description": "Simple chronic bronchitis", "hcc": "HCC048"},
    "J42": {"description": "Unspecified chronic bronchitis", "hcc": "HCC048"},
    "J43": {"description": "Emphysema", "hcc": "HCC048"},
    "J44": {"description": "Chronic obstructive pulmonary disease", "hcc": "HCC048"},
    "I63": {"description": "Cerebral infarction", "hcc": "HCC051"},
    "I64": {"description": "Stroke, not specified as hemorrhage or infarction", "hcc": "HCC051"},
    "I73": {"description": "Other peripheral vascular diseases", "hcc": "HCC052"},
    "I74": {"description": "Arterial embolism and thrombosis", "hcc": "HCC052"},
    "I10": {"description": "Essential (primary) hypertension", "hcc": "HCC053"},
    "I11": {"description": "Hypertensive heart disease", "hcc": "HCC053"},
    "I12": {"description": "Hypertensive chronic kidney disease", "hcc": "HCC053"},
    
    # Respiratory System Diseases
    "E84": {"description": "Cystic fibrosis", "hcc": "HCC112"},
    "J84": {"description": "Other interstitial pulmonary diseases", "hcc": "HCC113"},
    
    # Genitourinary System
    "N18.5": {"description": "Chronic kidney disease, stage 5", "hcc": "HCC134"},
    "N18.3": {"description": "Chronic kidney disease, stage 3a", "hcc": "HCC135"},
    "N18.4": {"description": "Chronic kidney disease, stage 4", "hcc": "HCC135"},
    
    # Mental, Behavioral and Neurodevelopmental Disorders
    "F20": {"description": "Schizophrenia", "hcc": "HCC157"},
    "F32": {"description": "Depressive episode", "hcc": "HCC158"},
    "F33": {"description": "Recurrent depressive disorder", "hcc": "HCC158"},
    
    # Diseases of the Musculoskeletal System and Connective Tissue
    "M05": {"description": "Rheumatoid arthritis with rheumatoid factor", "hcc": "HCC164"},
    "M06": {"description": "Other rheumatoid arthritis", "hcc": "HCC164"},
}

# Keyword to ICD-10 code mapping for easier lookup
CONDITION_TO_ICD10 = {
    "diabetes": ["E10.9", "E11.9", "E13.9"],
    "diabetes type 1": ["E10.9"],
    "diabetes type 2": ["E11.9"],
    "heart failure": ["I50"],
    "hypertension": ["I10", "I11", "I12"],
    "copd": ["J44"],
    "stroke": ["I63", "I64"],
    "asthma": ["J45"],
    "pneumonia": ["J15", "J16", "J18"],
    "sepsis": ["A40", "A41"],
    "cancer": ["C80"],
    "lung cancer": ["C34"],
    "breast cancer": ["C50"],
    "hiv": ["B20"],
    "ckd": ["N18"],
    "heart attack": ["I21"],
    "depression": ["F32", "F33"],
}


class ICD10Mapper:
    """ICD-10-CM code mapper and validator"""
    
    def __init__(self):
        self.codes_db = ICD10_CODES_DB
        self.condition_map = CONDITION_TO_ICD10
    
    def validate_icd10_code(self, code: str) -> Tuple[bool, str]:
        """
        Validate ICD-10-CM code format.
        
        Args:
            code: ICD-10-CM code to validate
        
        Returns:
            Tuple of (is_valid, message)
        """
        code = code.strip().upper()
        
        if not re.match(ICD10_PATTERN, code):
            return False, f"Invalid format: {code} (expected: A##, A##.#, or A##.##)"
        
        # Check if code exists in database
        base_code = code.split('.')[0]
        if base_code in self.codes_db or code in self.codes_db:
            return True, "Valid ICD-10-CM code"
        
        # Code format is valid but not in database (could be new/future code)
        return True, "Valid format (code not in database)"
    
    def get_icd10_description(self, code: str) -> str:
        """Get description for ICD-10 code"""
        code = code.strip().upper()
        
        if code in self.codes_db:
            return self.codes_db[code]["description"]
        
        # Try base code
        base_code = code.split('.')[0]
        if base_code in self.codes_db:
            return self.codes_db[base_code]["description"]
        
        return "Description not found"
    
    def get_hcc_from_icd10(self, code: str) -> str:
        """Get HCC code for given ICD-10 code"""
        code = code.strip().upper()
        
        if code in self.codes_db:
            return self.codes_db[code].get("hcc", None)
        
        # Try base code
        base_code = code.split('.')[0]
        if base_code in self.codes_db:
            return self.codes_db[base_code].get("hcc", None)
        
        return None
    
    def find_icd10_by_condition(self, condition: str) -> List[Dict]:
        """Find ICD-10 codes that match a condition"""
        condition_lower = condition.lower().strip()
        results = []
        
        # Check condition map
        if condition_lower in self.condition_map:
            for code in self.condition_map[condition_lower]:
                if code in self.codes_db:
                    results.append({
                        "code": code,
                        "description": self.codes_db[code]["description"],
                        "hcc": self.codes_db[code].get("hcc", None)
                    })
        
        # Also search by keyword in descriptions
        for code, details in self.codes_db.items():
            if condition_lower in details["description"].lower():
                if code not in [r["code"] for r in results]:
                    results.append({
                        "code": code,
                        "description": details["description"],
                        "hcc": details.get("hcc", None)
                    })
        
        return results[:10]  # Limit to 10 results
    
    def suggest_icd10_codes(self, partial_text: str) -> List[Dict]:
        """Suggest ICD-10 codes based on partial text"""
        partial_lower = partial_text.lower().strip()
        suggestions = []
        
        for code, details in self.codes_db.items():
            if partial_lower in code.lower() or partial_lower in details["description"].lower():
                suggestions.append({
                    "code": code,
                    "description": details["description"],
                    "hcc": details.get("hcc", None)
                })
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def validate_code_sequence(self, codes: List[str]) -> Dict:
        """Validate a sequence of ICD-10 codes for conflicts"""
        validation = {
            "valid_codes": [],
            "invalid_codes": [],
            "warnings": [],
            "conflicts": []
        }
        
        for code in codes:
            is_valid, msg = self.validate_icd10_code(code)
            if is_valid:
                validation["valid_codes"].append(code)
            else:
                validation["invalid_codes"].append({"code": code, "error": msg})
        
        # Check for hierarchy conflicts (handled by HCC engine)
        # This is where you'd implement additional validation logic
        
        return validation


# Backward compatibility functions
def extract_diagnoses(text: str) -> Dict:
    """Extract diagnoses from text (backward compatibility)"""
    mapper = ICD10Mapper()
    diagnoses_found = {}
    
    for condition, codes in CONDITION_TO_ICD10.items():
        if re.search(rf"\b{condition}\b", text.lower()):
            for code in codes:
                diagnoses_found[condition] = code
                break
    
    return diagnoses_found
