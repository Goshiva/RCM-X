"""
Machine Learning Model for HCC Code Prediction
Provides advanced code suggestion and prediction based on medical entities
"""

import json
from typing import Dict, List, Tuple
from collections import Counter
import logging

logger = logging.getLogger(__name__)

# Training data for ML model - medical conditions to HCC codes mapping
CONDITION_TO_HCC_MAPPING = {
    # Infectious & Parasitic
    "hiv": ["HCC001"],
    "aids": ["HCC001"],
    "septicemia": ["HCC002"],
    "meningitis": ["HCC002"],
    "tuberculosis": ["HCC006"],
    
    # Neoplasms
    "metastatic cancer": ["HCC008"],
    "lung cancer": ["HCC010"],
    "breast cancer": ["HCC011"],
    "colorectal cancer": ["HCC012"],
    "acute leukemia": ["HCC017"],
    
    # Endocrine
    "diabetes type 1": ["HCC035", "HCC036"],
    "diabetes type 2": ["HCC035", "HCC036"],
    "diabetic complications": ["HCC036"],
    "thyroid disease": ["HCC037"],
    
    # Circulatory
    "heart failure": ["HCC047"],
    "acute mi": ["HCC046"],
    "copd": ["HCC048"],
    "cerebrovascular disease": ["HCC051"],
    "peripheral vascular disease": ["HCC052"],
    "hypertension": ["HCC053"],
    "stroke": ["HCC051"],
    "arrhythmia": ["HCC046", "HCC047"],
    
    # Respiratory
    "chronic respiratory conditions": ["HCC111"],
    "cystic fibrosis": ["HCC112"],
    "lung disease": ["HCC113"],
    "asthma": ["HCC111"],
    "pneumonia": ["HCC113"],
    
    # Kidney
    "chronic kidney disease": ["HCC134", "HCC135"],
    "end-stage renal": ["HCC134"],
    
    # Psychiatric
    "schizophrenia": ["HCC157"],
    "depression": ["HCC158"],
    "anxiety": ["HCC158"],
    "bipolar": ["HCC158"],
    
    # Musculoskeletal
    "rheumatoid arthritis": ["HCC164"],
    "osteoarthritis": ["HCC164"],
    "lupus": ["HCC164"],
    
    # Neurological
    "dementia": ["HCC159"],
    "parkinson": ["HCC160"],
    "multiple sclerosis": ["HCC160"],
    "seizure": ["HCC161"],
}

# Medication to HCC mapping - medications that indicate certain conditions
MEDICATION_TO_HCC_MAPPING = {
    # Cardiac medications
    "metoprolol": ["HCC046", "HCC047", "HCC053"],
    "lisinopril": ["HCC047", "HCC053"],
    "atorvastatin": ["HCC046", "HCC053"],
    "warfarin": ["HCC046"],
    
    # Diabetes medications
    "metformin": ["HCC035", "HCC036"],
    "insulin": ["HCC035", "HCC036"],
    "glipizide": ["HCC035", "HCC036"],
    
    # COPD medications
    "albuterol": ["HCC048", "HCC111"],
    "ipratropium": ["HCC048"],
    
    # Psychiatric medications
    "sertraline": ["HCC158"],
    "fluoxetine": ["HCC158"],
    "haloperidol": ["HCC157"],
    
    # CKD medications
    "amlodipine": ["HCC135"],
}

# Lab values thresholds for HCC prediction
LAB_VALUE_THRESHOLDS = {
    "HbA1c": {
        "threshold": 7.5,
        "hcc_codes": ["HCC035", "HCC036"],
        "condition": "Diabetes with complications"
    },
    "egfr": {
        "threshold": 30,
        "hcc_codes": ["HCC134"],
        "condition": "CKD Stage 5"
    },
    "bmi": {
        "threshold": 40,
        "hcc_codes": ["HCC021"],
        "condition": "Morbid Obesity"
    }
}


class HCCPredictionModel:
    """Machine learning model for HCC code prediction"""
    
    def __init__(self):
        self.confidence_scores = {}
        self.feature_weights = {
            "condition_match": 0.6,
            "medication_support": 0.25,
            "lab_value_support": 0.15,
        }
    
    def predict_hcc_codes(self, medical_entities: Dict, icd10_codes: List[str] = None) -> List[Dict]:
        """
        Predict HCC codes based on medical entities with confidence scores.
        
        Args:
            medical_entities: Dict with medical conditions, medications, lab values
            icd10_codes: Optional list of ICD-10 codes already assigned
        
        Returns:
            List of predicted HCC codes with confidence scores
        """
        predictions = {}
        
        # Score from medical conditions
        conditions = medical_entities.get("medical_conditions", [])
        for condition in conditions:
            # Normalize condition name for matching - try multiple variations
            norm_condition = condition.lower().strip()
            variations = [
                norm_condition,
                norm_condition.replace("type 2 ", "type 2 "),  # type 2 diabetes -> diabetes type 2
                norm_condition.replace("type 1 ", "type 1 "),
            ]
            # Also try swapping "diabetes type 2" <-> "type 2 diabetes"
            if "diabetes" in norm_condition and "type 2" in norm_condition:
                variations.append("diabetes type 2")
                variations.append("type 2 diabetes")
            if "diabetes" in norm_condition and "type 1" in norm_condition:
                variations.append("diabetes type 1")
                variations.append("type 1 diabetes")
            
            hcc_codes = []
            for var in variations:
                hcc_codes = CONDITION_TO_HCC_MAPPING.get(var, [])
                if hcc_codes:
                    break
            
            for code in hcc_codes:
                if code not in predictions:
                    predictions[code] = 0.0
                predictions[code] += self.feature_weights["condition_match"]
        
        # Score from medications
        medications = medical_entities.get("medications", [])
        for med in medications:
            hcc_codes = MEDICATION_TO_HCC_MAPPING.get(med, [])
            for code in hcc_codes:
                if code not in predictions:
                    predictions[code] = 0.0
                predictions[code] += self.feature_weights["medication_support"]
        
        # Score from lab values
        lab_values = medical_entities.get("lab_values", {})
        for lab_name, lab_value in lab_values.items():
            if lab_name in LAB_VALUE_THRESHOLDS:
                try:
                    value = float(lab_value)
                    threshold = LAB_VALUE_THRESHOLDS[lab_name]["threshold"]
                    
                    # Check if lab value exceeds threshold
                    if (lab_name == "egfr" and value < threshold) or \
                       (lab_name in ["HbA1c", "bmi"] and value > threshold):
                        hcc_codes = LAB_VALUE_THRESHOLDS[lab_name]["hcc_codes"]
                        for code in hcc_codes:
                            if code not in predictions:
                                predictions[code] = 0.0
                            predictions[code] += self.feature_weights["lab_value_support"]
                except (ValueError, TypeError):
                    continue
        
        # Convert to sorted list with confidence scores
        result = []
        for hcc_code, score in sorted(predictions.items(), key=lambda x: x[1], reverse=True):
            if score > 0:
                result.append({
                    "hcc_code": hcc_code,
                    "confidence": round(min(score, 1.0), 3),
                    "evidence": self._get_evidence(hcc_code, medical_entities)
                })
        
        return result
    
    def _get_evidence(self, hcc_code: str, medical_entities: Dict) -> str:
        """Generate evidence string for HCC prediction"""
        evidence = []
        
        conditions = medical_entities.get("medical_conditions", [])
        for condition in conditions:
            if hcc_code in CONDITION_TO_HCC_MAPPING.get(condition, []):
                evidence.append(f"Condition: {condition}")
        
        medications = medical_entities.get("medications", [])
        for med in medications:
            if hcc_code in MEDICATION_TO_HCC_MAPPING.get(med, []):
                evidence.append(f"Medication: {med}")
        
        lab_values = medical_entities.get("lab_values", {})
        for lab_name, lab_value in lab_values.items():
            if lab_name in LAB_VALUE_THRESHOLDS:
                if hcc_code in LAB_VALUE_THRESHOLDS[lab_name]["hcc_codes"]:
                    evidence.append(f"Lab: {lab_name}={lab_value}")
        
        return " | ".join(evidence) if evidence else "ML-predicted"
    
    def validate_hcc_code(self, hcc_code: str, confidence_threshold: float = 0.5) -> bool:
        """Validate if HCC code meets confidence threshold"""
        return self.confidence_scores.get(hcc_code, 0) >= confidence_threshold
    
    def get_code_suggestions(self, partial_text: str, limit: int = 5) -> List[str]:
        """Get HCC code suggestions based on partial text"""
        # This could be enhanced with fuzzy matching
        suggestions = []
        text_lower = partial_text.lower()
        
        for condition, codes in CONDITION_TO_HCC_MAPPING.items():
            if text_lower in condition:
                suggestions.extend(codes)
        
        return list(set(suggestions))[:limit]
