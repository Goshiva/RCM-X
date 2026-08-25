import re
from typing import Dict, List, Tuple

# Comprehensive medical condition database
MEDICAL_CONDITIONS_DB = {
    # Cardiovascular
    "heart failure": ["heart failure", "cardiac failure", "decompensated", "CHF"],
    "acute mi": ["acute myocardial", "AMI", "acute MI", "heart attack"],
    "hypertension": ["hypertension", "high blood pressure", "HTN"],
    "arrhythmia": ["atrial fibrillation", "AFib", "arrhythmia", "irregular heartbeat"],
    "stroke": ["cerebrovascular", "stroke", "CVA", "transient ischemic"],
    
    # Respiratory
    "copd": ["COPD", "emphysema", "chronic obstructive", "chronic bronchitis"],
    "asthma": ["asthma", "reactive airway"],
    "pneumonia": ["pneumonia", "community-acquired", "CAP"],
    "pulmonary fibrosis": ["pulmonary fibrosis", "IPF", "interstitial lung"],
    
    # Endocrine
    "diabetes type 1": ["diabetes type 1", "type 1 diabetes", "insulin dependent", "T1DM"],
    "diabetes type 2": ["diabetes type 2", "type 2 diabetes", "non-insulin dependent", "T2DM"],
    "diabetic complications": ["diabetic retinopathy", "diabetic nephropathy", "neuropathy"],
    "thyroid disease": ["hyperthyroid", "hypothyroid", "thyroid disorder"],
    
    # Metabolic
    "obesity": ["obesity", "morbid obesity", "BMI"],
    "hyperlipidemia": ["hyperlipidemia", "high cholesterol"],
    
    # Renal
    "chronic kidney disease": ["chronic kidney disease", "CKD", "renal failure"],
    "end-stage renal": ["ESRD", "end-stage renal", "dialysis"],
    
    # Malignancy
    "cancer": ["cancer", "malignancy", "neoplasm", "carcinoma", "tumor"],
    "metastatic cancer": ["metastatic", "stage IV", "secondary cancer"],
    
    # Psychiatric
    "depression": ["depression", "major depressive", "depressive disorder"],
    "schizophrenia": ["schizophrenia", "psychotic"],
    "bipolar": ["bipolar disorder", "manic depressive"],
    "anxiety": ["anxiety disorder", "panic disorder"],
    
    # Rheumatologic
    "rheumatoid arthritis": ["rheumatoid arthritis", "RA"],
    "lupus": ["lupus", "SLE", "systemic lupus"],
    "osteoarthritis": ["osteoarthritis", "OA", "degenerative joint"],
    
    # Neurological
    "dementia": ["dementia", "Alzheimer", "cognitive decline"],
    "parkinson": ["Parkinson", "parkinsonism"],
    "multiple sclerosis": ["multiple sclerosis", "MS"],
    "seizure": ["seizure", "epilepsy", "epileptic"],
    
    # Infectious
    "hiv": ["HIV", "AIDS", "human immunodeficiency"],
    "hepatitis": ["hepatitis", "viral hepatitis"],
}

# Medication database for extraction
MEDICATIONS_DB = {
    # Cardiovascular
    "lisinopril": ["lisinopril", "Prinivil"],
    "metoprolol": ["metoprolol", "Lopressor"],
    "atorvastatin": ["atorvastatin", "Lipitor"],
    "warfarin": ["warfarin", "Coumadin"],
    
    # Diabetes
    "metformin": ["metformin", "Glucophage"],
    "insulin": ["insulin", "glargine", "lispro"],
    "glipizide": ["glipizide", "Glucotrol"],
    
    # Pain/Anti-inflammatory
    "aspirin": ["aspirin"],
    "ibuprofen": ["ibuprofen", "Advil"],
    "naproxen": ["naproxen", "Aleve"],
    
    # Psychiatric
    "sertraline": ["sertraline", "Zoloft"],
    "fluoxetine": ["fluoxetine", "Prozac"],
    "escitalopram": ["escitalopram", "Lexapro"],
    
    # Antibiotics
    "amoxicillin": ["amoxicillin", "Amoxil"],
    "ciprofloxacin": ["ciprofloxacin", "Cipro"],
    "azithromycin": ["azithromycin", "Z-pack"],
}

# Lab values patterns
LAB_VALUES = {
    "HbA1c": r'(?:HbA1c|A1C|glycohemoglobin)[:\s]+(\d+\.?\d*)',
    "blood_glucose": r'(?:glucose|blood sugar)[:\s]+(\d+)',
    "creatinine": r'(?:creatinine|Cr)[:\s]+(\d+\.?\d*)',
    "egfr": r'(?:eGFR|GFR)[:\s]+(\d+)',
    "bmi": r'(?:BMI)[:\s]+(\d+\.?\d*)',
}

def extract_medical_entities(text: str) -> Dict:
    """
    Extract medical entities from OCR text using advanced pattern matching.
    Focuses on healthcare-relevant information only.
    
    Returns:
        Dictionary with identified medical entities
    """
    entities = {
        "person_names": [],
        "patient_id": None,
        "dates": [],
        "medical_conditions": [],
        "medications": [],
        "lab_values": {},
        "vital_signs": []
    }
    
    text_lower = text.lower()
    
    # Extract person names (capitalized words after "Patient" or "Name")
    person_pattern = r'(?:Patient|Name|Dr\.|Physician)[:\s]+\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
    person_matches = re.findall(person_pattern, text)
    entities["person_names"] = list(set(person_matches))
    
    # Extract patient/medical record ID
    id_patterns = [
        r'(?:Patient ID|MRN|Medical Record)[:\s]+\s*([A-Z0-9\-]+)',
        r'ID[:\s]+([A-Z0-9\-]{5,})',
    ]
    for pattern in id_patterns:
        id_match = re.search(pattern, text, re.IGNORECASE)
        if id_match:
            entities["patient_id"] = id_match.group(1)
            break
    
    # Extract dates (various medical report date formats)
    date_pattern = r'(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})'
    date_matches = re.findall(date_pattern, text, re.IGNORECASE)
    entities["dates"] = list(set(date_matches))
    
    # Extract medical conditions with improved matching
    for condition_name, condition_terms in MEDICAL_CONDITIONS_DB.items():
        for term in condition_terms:
            if re.search(rf'\b{re.escape(term)}\b', text_lower, re.IGNORECASE):
                entities["medical_conditions"].append(condition_name)
                break
    
    # Remove duplicates
    entities["medical_conditions"] = list(set(entities["medical_conditions"]))
    
    # Extract medications with improved matching
    for med_name, med_terms in MEDICATIONS_DB.items():
        for term in med_terms:
            if re.search(rf'\b{re.escape(term)}\b', text_lower, re.IGNORECASE):
                entities["medications"].append(med_name)
                break
    
    # Remove duplicates
    entities["medications"] = list(set(entities["medications"]))
    
    # Extract lab values
    for lab_name, lab_pattern in LAB_VALUES.items():
        lab_match = re.search(lab_pattern, text, re.IGNORECASE)
        if lab_match:
            entities["lab_values"][lab_name] = lab_match.group(1)
    
    # Extract vital signs
    vital_patterns = {
        "blood_pressure": r'(?:BP|blood pressure)[:\s]+(\d+/\d+)',
        "heart_rate": r'(?:HR|heart rate|pulse)[:\s]+(\d+)',
        "temperature": r'(?:temp|temperature|Temp)[:\s]+(\d+\.?\d*)',
        "oxygen_saturation": r'(?:O2 sat|SpO2)[:\s]+(\d+)',
    }
    for vital_name, vital_pattern in vital_patterns.items():
        vital_match = re.search(vital_pattern, text, re.IGNORECASE)
        if vital_match:
            entities["vital_signs"].append({
                "type": vital_name,
                "value": vital_match.group(1)
            })
    
    return entities


def identify_document_type(text: str) -> str:
    """
    Identify medical document type based on content.
    
    Returns:
        Document type string
    """
    text_lower = text.lower()
    
    # Medical document types
    if any(keyword in text_lower for keyword in ["discharge summary", "discharge note", "hospital discharge"]):
        return "discharge_summary"
    elif any(keyword in text_lower for keyword in ["office visit", "clinic note", "clinical note"]):
        return "office_visit"
    elif any(keyword in text_lower for keyword in ["prescription", "rx", "medications"]):
        return "prescription"
    elif any(keyword in text_lower for keyword in ["lab report", "laboratory result", "test results"]):
        return "lab_report"
    elif any(keyword in text_lower for keyword in ["imaging report", "radiology", "x-ray", "mri", "ct scan"]):
        return "imaging_report"
    elif any(keyword in text_lower for keyword in ["operative report", "surgery", "surgical", "post-op"]):
        return "operative_report"
    elif any(keyword in text_lower for keyword in ["progress note", "clinical progress", "follow-up"]):
        return "progress_note"
    elif any(keyword in text_lower for keyword in ["consultation", "consult note"]):
        return "consultation"
    else:
        return "medical_record"


def extract_nlp_insights(text: str) -> Dict:
    """
    Main function to extract all NLP insights from text.
    """
    insights = {
        "document_type": identify_document_type(text),
        "entities": extract_medical_entities(text),
        "text_length": len(text),
        "word_count": len(text.split()),
        "confidence": 0.85  # Base confidence score
    }
    
    # Adjust confidence based on entity extraction
    entities = insights["entities"]
    if entities["medical_conditions"] and entities["medications"]:
        insights["confidence"] = 0.95
    elif entities["medical_conditions"] or entities["medications"]:
        insights["confidence"] = 0.80
    elif entities["dates"] and entities["patient_id"]:
        insights["confidence"] = 0.70
    
    return insights
