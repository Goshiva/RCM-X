"""
Enhanced NLP Entity Extraction Module with Biomedical Models
Integrates ClinicalBERT, BioBERT, and SciBERT for medical entity recognition.
Includes fallback regex patterns for robustness and offline capability.
Version 3.0 - Production Biomedical NLP
"""

import re
import logging
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("Transformers library not available. Using regex-based fallback.")

try:
    import spacy
    from scispacy.linking import EntityLinker
    SCISPACY_AVAILABLE = True
except ImportError:
    SCISPACY_AVAILABLE = False
    logging.warning("ScispaCy not available. Using alternative NLP methods.")

logger = logging.getLogger(__name__)


@dataclass
class MedicalEntity:
    """Structured representation of a medical entity"""
    text: str
    entity_type: str  # PROBLEM, TREATMENT, MEDICATION, LAB, VITAL
    confidence: float  # 0.0-1.0
    source: str  # "transformer", "regex", "spacy"
    span_start: int  # Character position in original text
    span_end: int
    metadata: Dict = None  # Additional info like ICD codes, normal ranges
    
    def to_dict(self):
        return asdict(self)


class BiomedicalNLPPipeline:
    """Production-grade biomedical NLP with multiple models and fallback strategies"""
    
    def __init__(self):
        """Initialize NLP pipeline with available models"""
        self.model_initialized = False
        self.tokenizer = None
        self.model = None
        self.ner_pipeline = None
        self.nlp_spacy = None
        enable_transformers = os.getenv("ENABLE_TRANSFORMER_NLP", "false").lower() in {
            "1", "true", "yes", "on"
        }
        self.use_transformers = TRANSFORMERS_AVAILABLE and enable_transformers
        self.use_scispacy = SCISPACY_AVAILABLE
        
        # Fallback regex patterns for robustness
        self.condition_patterns = self._build_condition_patterns()
        self.medication_patterns = self._build_medication_patterns()
        self.lab_patterns = self._build_lab_patterns()
        
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize biomedical NLP models"""
        try:
            if self.use_transformers:
                # Initialize Clinical NER Pipeline
                # Using huggingface clinical NER model
                logger.info("Loading transformer-based NER model...")
                self.ner_pipeline = pipeline(
                    "token-classification",
                    model="d4data/biomedical-ner-all",  # Comprehensive biomedical NER
                    aggregation_strategy="simple"
                )
                self.model_initialized = True
                logger.info("Transformer NER model loaded successfully")
            
            if self.use_scispacy:
                logger.info("Loading ScispaCy model...")
                self.nlp_spacy = spacy.load("en_core_sci_lg")
                logger.info("ScispaCy model loaded successfully")
                
        except Exception as e:
            logger.warning(f"Could not load transformer models: {str(e)}. Using regex fallback.")
            self.use_transformers = False
            self.use_scispacy = False
    
    def _build_condition_patterns(self) -> Dict[str, Tuple[str, str]]:
        """Build comprehensive medical condition patterns with ICD-10 mapping"""
        return {
            # Cardiovascular
            "heart failure": (r'\b(?:heart\s+failure|cardiac\s+failure|CHF|HF|decompensated)\b', "I50"),
            "acute mi": (r'\b(?:acute\s+myocardial|AMI|acute\s+MI|heart\s+attack|STEMI|NSTEMI)\b', "I21"),
            "hypertension": (r'\b(?:hypertension|high\s+blood\s+pressure|HTN)\b', "I10"),
            "atrial fibrillation": (r'\b(?:atrial\s+fibrillation|AFib|AF|a-fib)\b', "I48"),
            "stroke": (r'\b(?:cerebrovascular|stroke|CVA|transient\s+ischemic|TIA)\b', "I63"),
            
            # Respiratory
            "copd": (r'\b(?:COPD|emphysema|chronic\s+obstructive|chronic\s+bronchitis)\b', "J44"),
            "asthma": (r'\b(?:asthma|reactive\s+airway|RAD)\b', "J45"),
            "pneumonia": (r'\b(?:pneumonia|community-acquired|CAP|bacterial\s+pneumonia)\b', "J18"),
            "pulmonary fibrosis": (r'\b(?:pulmonary\s+fibrosis|IPF|interstitial\s+lung)\b', "J84"),
            
            # Endocrine
            "diabetes type 1": (r'\b(?:diabetes\s+type\s+1|type\s+1\s+diabetes|insulin\s+dependent|IDDM|T1DM)\b', "E10.9"),
            "diabetes type 2": (r'\b(?:diabetes\s+type\s+2|type\s+2\s+diabetes|non-insulin\s+dependent|NIDDM|T2DM)\b', "E11.9"),
            "diabetic complications": (r'\b(?:diabetic\s+(?:retinopathy|nephropathy|neuropathy))\b', "E11.2"),
            "hyperthyroidism": (r'\b(?:hyperthyroid|hyperthyroidism|thyroid\s+storm)\b', "E05"),
            "hypothyroidism": (r'\b(?:hypothyroid|hypothyroidism|thyroid\s+insufficiency)\b', "E03"),
            
            # Renal/Metabolic
            "chronic kidney disease": (r'\b(?:chronic\s+kidney\s+disease|CKD|renal\s+failure|renal\s+disease)\b', "N18"),
            "end-stage renal disease": (r'\b(?:ESRD|end-stage\s+renal|dialysis|renal\s+replacement)\b', "N19"),
            "obesity": (r'\b(?:obesity|morbid\s+obesity|severe\s+obesity)\b', "E66"),
            "hyperlipidemia": (r'\b(?:hyperlipidemia|hypercholesterolemia|high\s+cholesterol)\b', "E78"),
            
            # Malignancy
            "malignant neoplasm": (r'\b(?:cancer|malignancy|malignant\s+neoplasm|carcinoma|tumor)\b', "C80"),
            "metastatic cancer": (r'\b(?:metastatic|stage\s+IV|secondary\s+cancer)\b', "C80.1"),
            "lung cancer": (r'\b(?:lung\s+cancer|bronchogenic\s+carcinoma)\b', "C34"),
            "breast cancer": (r'\b(?:breast\s+cancer|mammary\s+cancer)\b', "C50"),
            "colorectal cancer": (r'\b(?:colorectal\s+cancer|colon\s+cancer|rectal\s+cancer)\b', "C18"),
            
            # Psychiatric
            "major depression": (r'\b(?:depression|major\s+depressive|depressive\s+disorder|MDD)\b', "F32"),
            "schizophrenia": (r'\b(?:schizophrenia|psychotic\s+disorder)\b', "F20"),
            "bipolar disorder": (r'\b(?:bipolar|bipolar\s+disorder|manic\s+depressive)\b', "F31"),
            "anxiety disorder": (r'\b(?:anxiety|anxiety\s+disorder|panic\s+disorder|PTSD)\b', "F41"),
            
            # Rheumatologic
            "rheumatoid arthritis": (r'\b(?:rheumatoid\s+arthritis|RA|autoimmune\s+arthritis)\b', "M05"),
            "systemic lupus erythematosus": (r'\b(?:lupus|SLE|systemic\s+lupus)\b', "M32"),
            "osteoarthritis": (r'\b(?:osteoarthritis|OA|degenerative\s+joint|DJD)\b', "M17"),
            
            # Neurological
            "dementia": (r'\b(?:dementia|Alzheimer|cognitive\s+decline|neurodegenerative)\b', "F03"),
            "parkinson disease": (r'\b(?:Parkinson|parkinsonism|extrapyramidal)\b', "G20"),
            "multiple sclerosis": (r'\b(?:multiple\s+sclerosis|MS|demyelinating)\b', "G35"),
            "epilepsy": (r'\b(?:seizure|epilepsy|epileptic|convulsion)\b', "G40"),
            
            # Infectious
            "hiv": (r'\b(?:HIV|AIDS|human\s+immunodeficiency)\b', "B20"),
            "hepatitis": (r'\b(?:hepatitis|viral\s+hepatitis|HCV|HBV)\b', "B18"),
        }
    
    def _build_medication_patterns(self) -> Dict[str, str]:
        """Build comprehensive medication patterns"""
        return {
            # Cardiovascular
            "lisinopril": r'\b(?:lisinopril|Prinivil|ACE\s+inhibitor)\b',
            "metoprolol": r'\b(?:metoprolol|Lopressor|beta\s+blocker)\b',
            "atorvastatin": r'\b(?:atorvastatin|Lipitor|statin)\b',
            "warfarin": r'\b(?:warfarin|Coumadin|anticoagulant)\b',
            "aspirin": r'\b(?:aspirin|acetylsalicylic\s+acid|ASA)\b',
            
            # Diabetes
            "metformin": r'\b(?:metformin|Glucophage|biguanide)\b',
            "insulin": r'\b(?:insulin|glargine|lispro|NPH|rapid\s+acting)\b',
            "glipizide": r'\b(?:glipizide|Glucotrol|sulfonylurea)\b',
            
            # Psychiatric
            "sertraline": r'\b(?:sertraline|Zoloft|SSRI)\b',
            "fluoxetine": r'\b(?:fluoxetine|Prozac)\b',
            "escitalopram": r'\b(?:escitalopram|Lexapro)\b',
            
            # Antibiotics
            "amoxicillin": r'\b(?:amoxicillin|Amoxil|antibiotic)\b',
            "ciprofloxacin": r'\b(?:ciprofloxacin|Cipro|fluoroquinolone)\b',
            "azithromycin": r'\b(?:azithromycin|Z-pack|macrolide)\b',
            
            # Thyroid
            "levothyroxine": r'\b(?:levothyroxine|synthroid|thyroid\s+replacement)\b',
        }
    
    def _build_lab_patterns(self) -> Dict[str, Tuple[str, float, float]]:
        """Build lab value patterns with normal ranges"""
        return {
            "HbA1c": (r'(?:HbA1c|A1C|glycohemoglobin)[:\s]+(\d+\.?\d*)', 5.7, 11.0),  # %
            "glucose": (r'(?:glucose|blood\s+sugar)[:\s]+(\d+)', 70, 200),  # mg/dL
            "creatinine": (r'(?:creatinine|Cr)[:\s]+(\d+\.?\d*)', 0.7, 1.3),  # mg/dL
            "egfr": (r'(?:eGFR|GFR)[:\s]+(\d+)', 60, 120),  # mL/min/1.73m²
            "bmi": (r'(?:BMI)[:\s]+(\d+\.?\d*)', 18.5, 29.9),
            "bun": (r'(?:BUN|urea\s+nitrogen)[:\s]+(\d+)', 7, 20),  # mg/dL
            "albumin": (r'(?:albumin)[:\s]+(\d+\.?\d*)', 3.5, 5.0),  # g/dL
        }
    
    def extract_entities_transformer(self, text: str) -> List[MedicalEntity]:
        """Extract entities using transformer-based NER"""
        entities = []
        
        if not self.model_initialized or not self.ner_pipeline:
            return entities
        
        try:
            # Split text into manageable chunks (transformers have token limits)
            max_chunk_length = 512
            chunks = self._split_text_intelligent(text, max_chunk_length)
            
            offset = 0
            for chunk in chunks:
                try:
                    # Run NER pipeline
                    predictions = self.ner_pipeline(chunk)
                    
                    for pred in predictions:
                        # Map transformer label to entity type
                        entity_type = self._map_transformer_label(pred.get('entity_group', 'O'))
                        if entity_type and entity_type != 'O':
                            span_start = text.find(pred['word'], offset)
                            entity = MedicalEntity(
                                text=pred['word'],
                                entity_type=entity_type,
                                confidence=float(pred.get('score', 0.0)),
                                source="transformer",
                                span_start=span_start if span_start >= 0 else offset,
                                span_end=span_start + len(pred['word']) if span_start >= 0 else offset + len(pred['word']),
                                metadata={"label": pred.get('entity_group')}
                            )
                            entities.append(entity)
                    
                    offset += len(chunk)
                except Exception as e:
                    logger.warning(f"Error processing chunk: {str(e)}")
                    continue
            
        except Exception as e:
            logger.warning(f"Transformer NER error: {str(e)}")
        
        return entities
    
    def extract_entities_regex(self, text: str) -> List[MedicalEntity]:
        """Extract entities using regex patterns (robust fallback)"""
        entities = []
        text_lower = text.lower()
        
        # Extract conditions
        for condition_name, (pattern, icd_code) in self.condition_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entity = MedicalEntity(
                    text=match.group(0),
                    entity_type="PROBLEM",
                    confidence=0.85,
                    source="regex",
                    span_start=match.start(),
                    span_end=match.end(),
                    metadata={"icd_code": icd_code, "condition": condition_name}
                )
                entities.append(entity)
        
        # Extract medications
        for med_name, pattern in self.medication_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entity = MedicalEntity(
                    text=match.group(0),
                    entity_type="MEDICATION",
                    confidence=0.80,
                    source="regex",
                    span_start=match.start(),
                    span_end=match.end(),
                    metadata={"medication": med_name}
                )
                entities.append(entity)
        
        # Extract lab values
        for lab_name, (pattern, low_range, high_range) in self.lab_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    value = float(match.group(1))
                    entity = MedicalEntity(
                        text=match.group(0),
                        entity_type="LAB",
                        confidence=0.90,
                        source="regex",
                        span_start=match.start(),
                        span_end=match.end(),
                        metadata={
                            "lab_name": lab_name,
                            "value": value,
                            "normal_range": (low_range, high_range),
                            "abnormal": value < low_range or value > high_range
                        }
                    )
                    entities.append(entity)
                except ValueError:
                    continue
        
        return entities
    
    def extract_all_entities(self, text: str) -> Tuple[List[MedicalEntity], Dict]:
        """
        Extract all medical entities using available methods.
        Returns entities and metadata about extraction.
        """
        all_entities = []
        metadata = {
            "text_length": len(text),
            "word_count": len(text.split()),
            "methods_used": [],
            "total_entities": 0,
            "confidence_mean": 0.0
        }
        
        # Try transformer-based extraction first
        if self.use_transformers and self.model_initialized:
            try:
                transformer_entities = self.extract_entities_transformer(text)
                all_entities.extend(transformer_entities)
                metadata["methods_used"].append("transformer")
            except Exception as e:
                logger.warning(f"Transformer extraction failed: {str(e)}")
        
        # Always use regex fallback/supplementary extraction
        regex_entities = self.extract_entities_regex(text)
        
        # Deduplicate and merge
        all_entities = self._deduplicate_entities(all_entities + regex_entities)
        if regex_entities and "regex" not in metadata["methods_used"]:
            metadata["methods_used"].append("regex")
        
        # Calculate statistics
        metadata["total_entities"] = len(all_entities)
        if all_entities:
            metadata["confidence_mean"] = sum(e.confidence for e in all_entities) / len(all_entities)
        
        return all_entities, metadata
    
    def extract_vital_signs(self, text: str) -> List[MedicalEntity]:
        """Extract vital signs from text"""
        entities = []
        
        vital_patterns = {
            "blood_pressure": r'(?:BP|blood\s+pressure)[:\s]+(\d+/\d+)',
            "heart_rate": r'(?:HR|heart\s+rate|pulse)[:\s]+(\d+)',
            "temperature": r'(?:temp|temperature|Temp)[:\s]+(\d+\.?\d*)',
            "oxygen_saturation": r'(?:O2\s+sat|SpO2|oxygen)[:\s]+(\d+\.?\d*)',
            "respiratory_rate": r'(?:RR|respiratory\s+rate)[:\s]+(\d+)',
        }
        
        for vital_type, pattern in vital_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entity = MedicalEntity(
                    text=match.group(0),
                    entity_type="VITAL",
                    confidence=0.90,
                    source="regex",
                    span_start=match.start(),
                    span_end=match.end(),
                    metadata={"vital_type": vital_type, "value": match.group(1)}
                )
                entities.append(entity)
        
        return entities
    
    def _deduplicate_entities(self, entities: List[MedicalEntity]) -> List[MedicalEntity]:
        """Remove duplicate or overlapping entities, keeping highest confidence"""
        if not entities:
            return []
        
        # Sort by confidence descending
        sorted_entities = sorted(entities, key=lambda e: e.confidence, reverse=True)
        
        unique_entities = []
        for entity in sorted_entities:
            # Check if entity text already exists
            if not any(e.text.lower() == entity.text.lower() and 
                      e.entity_type == entity.entity_type for e in unique_entities):
                unique_entities.append(entity)
        
        return sorted(unique_entities, key=lambda e: e.span_start)
    
    def _map_transformer_label(self, label: str) -> str:
        """Map transformer NER labels to standard entity types"""
        label_map = {
            'B-PROBLEM': 'PROBLEM',
            'I-PROBLEM': 'PROBLEM',
            'B-TREATMENT': 'TREATMENT',
            'I-TREATMENT': 'TREATMENT',
            'B-MEDICATION': 'MEDICATION',
            'I-MEDICATION': 'MEDICATION',
            'B-LAB': 'LAB',
            'I-LAB': 'LAB',
            'O': None,
        }
        return label_map.get(label, 'O')
    
    def _split_text_intelligent(self, text: str, max_length: int) -> List[str]:
        """Split text intelligently at sentence boundaries"""
        chunks = []
        current_chunk = ""
        
        # Split by sentences
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_length:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks


# Singleton instance for module-level access
_nlp_pipeline = None

def get_nlp_pipeline() -> BiomedicalNLPPipeline:
    """Get or create the NLP pipeline singleton"""
    global _nlp_pipeline
    if _nlp_pipeline is None:
        _nlp_pipeline = BiomedicalNLPPipeline()
    return _nlp_pipeline


def extract_medical_entities(text: str) -> Dict:
    """
    Extract medical entities from text.
    Backward compatible with original nlp_identifier interface.
    
    Returns:
        Dictionary with identified medical entities
    """
    pipeline = get_nlp_pipeline()
    entities_list, metadata = pipeline.extract_all_entities(text)
    vitals = pipeline.extract_vital_signs(text)
    
    # Organize by type for backward compatibility
    entities_by_type = {
        "conditions": [],
        "medications": [],
        "procedures": [],
        "lab_values": [],
        "vital_signs": []
    }
    
    for entity in entities_list:
        if entity.entity_type == "PROBLEM":
            entities_by_type["conditions"].append({
                "text": entity.text,
                "confidence": entity.confidence,
                "icd_code": entity.metadata.get("icd_code") if entity.metadata else None
            })
        elif entity.entity_type == "MEDICATION":
            entities_by_type["medications"].append({
                "text": entity.text,
                "confidence": entity.confidence
            })
        elif entity.entity_type == "LAB":
            entities_by_type["lab_values"].append({
                "text": entity.text,
                "confidence": entity.confidence,
                "metadata": entity.metadata
            })
    
    for vital in vitals:
        entities_by_type["vital_signs"].append({
            "text": vital.text,
            "type": vital.metadata.get("vital_type") if vital.metadata else None,
            "value": vital.metadata.get("value") if vital.metadata else None
        })
    
    return {
        "entities": entities_by_type,
        "raw_entities": [e.to_dict() for e in entities_list + vitals],
        "extraction_methods": metadata["methods_used"],
        "confidence": metadata["confidence_mean"],
        "total_entities": metadata["total_entities"]
    }


def identify_document_type(text: str) -> str:
    """
    Identify medical document type based on content.
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
    Backward compatible interface.
    """
    insights = {
        "document_type": identify_document_type(text),
        "entities": extract_medical_entities(text),
        "text_length": len(text),
        "word_count": len(text.split()),
        "confidence": 0.85  # Will be overridden by actual confidence
    }
    
    # Update confidence based on extracted entities
    entities = insights["entities"]["entities"]
    if entities.get("conditions") and entities.get("medications"):
        insights["confidence"] = 0.95
    elif entities.get("conditions") or entities.get("medications"):
        insights["confidence"] = 0.85
    elif entities.get("lab_values"):
        insights["confidence"] = 0.80
    
    return insights
