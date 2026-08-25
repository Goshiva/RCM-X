"""
Enhanced ICD-10-CM Code Mapper with ML Classification
Includes hybrid lookup, semantic matching, and ML-based classification for ambiguous codes.
Version 3.0 - Production ML-enhanced Mapping
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import json

try:
    from transformers import pipeline, AutoTokenizer, AutoModel
    import torch
    import numpy as np
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    np = None
    logging.warning("Transformers not available. Using database lookup only.")

try:
    from sklearn.preprocessing import normalize
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("Scikit-learn not available.")

logger = logging.getLogger(__name__)

# ICD-10-CM code validation pattern
ICD10_PATTERN = r'^[A-Z]\d{2}(?:\.\d{1,2})?$'

# Comprehensive ICD-10-CM codes database (expanded version)
ICD10_CODES_DB = {
    # Infectious Diseases
    "B20": {"description": "Human immunodeficiency virus [HIV] disease", "hcc": "HCC001", "keywords": ["hiv", "aids", "immunodeficiency"]},
    "A40": {"description": "Streptococcal sepsis", "hcc": "HCC002", "keywords": ["streptococcal", "sepsis"]},
    "A41": {"description": "Other sepsis", "hcc": "HCC002", "keywords": ["sepsis", "septic"]},
    "G00": {"description": "Bacterial meningitis", "hcc": "HCC002", "keywords": ["meningitis", "bacterial"]},
    "A15": {"description": "Respiratory tuberculosis", "hcc": "HCC006", "keywords": ["tuberculosis", "tb"]},
    
    # Malignant Neoplasms
    "C80": {"description": "Malignant neoplasm, unspecified", "hcc": "HCC008", "keywords": ["cancer", "malignant", "neoplasm"]},
    "C34": {"description": "Malignant neoplasm of unspecified part of unspecified bronchus or lung", "hcc": "HCC010", "keywords": ["lung cancer", "bronchus"]},
    "C50": {"description": "Malignant neoplasm of breast", "hcc": "HCC011", "keywords": ["breast cancer"]},
    "C18": {"description": "Malignant neoplasm of colon", "hcc": "HCC012", "keywords": ["colon cancer", "colorectal"]},
    "C91": {"description": "Lymphoid leukemia", "hcc": "HCC017", "keywords": ["leukemia", "lymphoid"]},
    
    # Endocrine Diseases
    "E10.9": {"description": "Type 1 diabetes mellitus without complications", "hcc": "HCC035", "keywords": ["type 1 diabetes", "insulin dependent"]},
    "E11.9": {"description": "Type 2 diabetes mellitus without complications", "hcc": "HCC035", "keywords": ["type 2 diabetes", "non-insulin"]},
    "E10.65": {"description": "Type 1 diabetes with hyperglycemia", "hcc": "HCC036", "keywords": ["diabetes", "hyperglycemia"]},
    "E01": {"description": "Iodine-deficiency-related thyroid disorders", "hcc": "HCC037", "keywords": ["thyroid", "iodine"]},
    
    # Circulatory System Diseases
    "I21": {"description": "Myocardial infarction", "hcc": "HCC046", "keywords": ["heart attack", "mi", "ami"]},
    "I50": {"description": "Heart failure", "hcc": "HCC047", "keywords": ["heart failure", "cardiac", "chf"]},
    "J44": {"description": "Chronic obstructive pulmonary disease", "hcc": "HCC048", "keywords": ["copd", "emphysema"]},
    "I63": {"description": "Cerebral infarction", "hcc": "HCC051", "keywords": ["stroke", "infarction"]},
    "I10": {"description": "Essential hypertension", "hcc": "HCC053", "keywords": ["hypertension", "high blood pressure"]},
    
    # Mental, Behavioral Disorders
    "F20": {"description": "Schizophrenia", "hcc": "HCC157", "keywords": ["schizophrenia", "psychotic"]},
    "F32": {"description": "Depressive episode", "hcc": "HCC158", "keywords": ["depression", "depressive"]},
    "F33": {"description": "Recurrent depressive disorder", "hcc": "HCC158", "keywords": ["depression", "recurrent"]},
    
    # Rheumatologic
    "M05": {"description": "Rheumatoid arthritis", "hcc": "HCC164", "keywords": ["rheumatoid", "arthritis", "ra"]},
    "M06": {"description": "Other rheumatoid arthritis", "hcc": "HCC164", "keywords": ["arthritis"]},
    
    # Renal
    "N18": {"description": "Chronic kidney disease", "hcc": "HCC135", "keywords": ["kidney disease", "renal", "ckd"]},
    "N19": {"description": "Unspecified kidney failure", "hcc": "HCC136", "keywords": ["kidney failure", "renal failure"]},
}

# Keyword to ICD-10 code mapping
CONDITION_TO_ICD10 = {
    "diabetes": ["E10.9", "E11.9"],
    "heart failure": ["I50"],
    "hypertension": ["I10"],
    "copd": ["J44"],
    "stroke": ["I63"],
    "heart attack": ["I21"],
    "cancer": ["C80"],
    "depression": ["F32", "F33"],
    "arthritis": ["M05", "M06"],
    "kidney disease": ["N18"],
}


@dataclass
class MappingResult:
    """Result of ICD-10 code mapping"""
    code: str
    description: str
    hcc: Optional[str]
    confidence: float  # 0.0-1.0
    source: str  # "database", "ml_classifier", "semantic"
    alternatives: List[Dict] = None  # Alternative codes
    metadata: Dict = None
    
    def to_dict(self):
        return {
            "code": self.code,
            "description": self.description,
            "hcc": self.hcc,
            "confidence": self.confidence,
            "source": self.source,
            "alternatives": self.alternatives or [],
            "metadata": self.metadata or {}
        }


class EnhancedICD10Mapper:
    """ICD-10 mapper with ML classification and semantic matching"""
    
    def __init__(self):
        """Initialize the mapper with models"""
        self.codes_db = ICD10_CODES_DB
        self.condition_map = CONDITION_TO_ICD10
        
        # Initialize semantic similarity model if available
        self.semantic_model = None
        self.tokenizer = None
        self.use_semantic = False
        
        if TRANSFORMERS_AVAILABLE:
            self._init_semantic_model()
        
        # ML classifier for ambiguous terms
        self.ml_classifier = None
        if TRANSFORMERS_AVAILABLE:
            try:
                self.ml_classifier = pipeline(
                    "zero-shot-classification",
                    model="facebook/bart-large-mnli"
                )
                logger.info("ML classifier initialized successfully")
            except Exception as e:
                logger.warning(f"Could not load ML classifier: {str(e)}")
    
    def _init_semantic_model(self):
        """Initialize semantic similarity model"""
        try:
            # Use biomedical BERT for semantic similarity
            model_name = "dmis-lab/biobert-v1.1"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.semantic_model = AutoModel.from_pretrained(model_name)
            self.use_semantic = True
            logger.info("Semantic model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load semantic model: {str(e)}")
            self.use_semantic = False
    
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
        
        return True, "Valid format (code not in database)"
    
    def get_icd10_description(self, code: str) -> str:
        """Get description for ICD-10 code"""
        code = code.strip().upper()
        
        if code in self.codes_db:
            return self.codes_db[code]["description"]
        
        base_code = code.split('.')[0]
        if base_code in self.codes_db:
            return self.codes_db[base_code]["description"]
        
        return "Description not found"
    
    def get_hcc_from_icd10(self, code: str) -> Optional[str]:
        """Get HCC code for given ICD-10 code"""
        code = code.strip().upper()
        
        if code in self.codes_db:
            return self.codes_db[code].get("hcc", None)
        
        base_code = code.split('.')[0]
        if base_code in self.codes_db:
            return self.codes_db[base_code].get("hcc", None)
        
        return None
    
    def find_icd10_by_condition(self, condition: str) -> List[MappingResult]:
        """Find ICD-10 codes matching a condition"""
        condition_lower = condition.lower().strip()
        results = []
        
        # Check condition map first (exact match)
        if condition_lower in self.condition_map:
            for code in self.condition_map[condition_lower]:
                if code in self.codes_db:
                    results.append(MappingResult(
                        code=code,
                        description=self.codes_db[code]["description"],
                        hcc=self.codes_db[code].get("hcc"),
                        confidence=0.95,
                        source="database"
                    ))
        
        # Search by keyword match
        for code, details in self.codes_db.items():
            if any(keyword in condition_lower for keyword in details.get("keywords", [])):
                if not any(r.code == code for r in results):
                    results.append(MappingResult(
                        code=code,
                        description=details["description"],
                        hcc=details.get("hcc"),
                        confidence=0.85,
                        source="database"
                    ))
        
        # Try semantic matching if available
        if self.use_semantic and len(results) < 5:
            semantic_results = self._semantic_search(condition)
            for sr in semantic_results:
                if not any(r.code == sr.code for r in results):
                    results.append(sr)
        
        # Sort by confidence and limit results
        results = sorted(results, key=lambda r: r.confidence, reverse=True)[:10]
        return results
    
    def _semantic_search(self, text: str) -> List[MappingResult]:
        """Use semantic similarity to find similar codes"""
        results = []
        
        if not self.use_semantic:
            return results
        
        try:
            # Get embedding for input text
            input_embedding = self._get_embedding(text)
            
            # Compare with code descriptions
            similarities = []
            for code, details in self.codes_db.items():
                code_embedding = self._get_embedding(details["description"])
                similarity = self._cosine_similarity(input_embedding, code_embedding)
                similarities.append((code, details, similarity))
            
            # Sort by similarity and get top results
            similarities.sort(key=lambda x: x[2], reverse=True)
            
            for code, details, similarity in similarities[:3]:
                if similarity > 0.5:  # Threshold for semantic match
                    results.append(MappingResult(
                        code=code,
                        description=details["description"],
                        hcc=details.get("hcc"),
                        confidence=float(similarity),
                        source="semantic"
                    ))
        
        except Exception as e:
            logger.warning(f"Semantic search error: {str(e)}")
        
        return results
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text using biomedical BERT"""
        if not self.tokenizer or not self.semantic_model:
            return np.zeros(768)
        
        try:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            with torch.no_grad():
                outputs = self.semantic_model(**inputs)
                embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()
            return embedding
        except Exception as e:
            logger.warning(f"Embedding error: {str(e)}")
            return np.zeros(768)
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        if SKLEARN_AVAILABLE:
            try:
                similarity = cosine_similarity([vec1], [vec2])[0][0]
                return float(similarity)
            except:
                pass
        
        # Fallback calculation
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def classify_ambiguous_code(self, medical_text: str, candidate_codes: List[str]) -> MappingResult:
        """
        Use ML classifier to determine best ICD-10 code from candidates.
        Useful when multiple codes could apply.
        """
        if not self.ml_classifier or len(candidate_codes) < 2:
            # Fall back to first candidate
            if candidate_codes:
                code = candidate_codes[0].upper()
                return MappingResult(
                    code=code,
                    description=self.get_icd10_description(code),
                    hcc=self.get_hcc_from_icd10(code),
                    confidence=0.7,
                    source="database"
                )
            return None
        
        try:
            # Prepare candidate descriptions
            candidate_labels = []
            for code in candidate_codes:
                code_upper = code.upper()
                desc = self.get_icd10_description(code_upper)
                candidate_labels.append(f"{code_upper}: {desc}")
            
            # Use zero-shot classification
            result = self.ml_classifier(medical_text, candidate_labels)
            
            # Get best match
            best_label = result["labels"][0]
            best_code = best_label.split(":")[0].strip()
            confidence = float(result["scores"][0])
            
            return MappingResult(
                code=best_code,
                description=self.get_icd10_description(best_code),
                hcc=self.get_hcc_from_icd10(best_code),
                confidence=confidence,
                source="ml_classifier",
                alternatives=[
                    {"code": code.split(":")[0].strip(), "score": float(score)}
                    for code, score in zip(result["labels"][1:], result["scores"][1:])
                ]
            )
        
        except Exception as e:
            logger.warning(f"Classification error: {str(e)}")
            # Fall back to first candidate
            if candidate_codes:
                code = candidate_codes[0].upper()
                return MappingResult(
                    code=code,
                    description=self.get_icd10_description(code),
                    hcc=self.get_hcc_from_icd10(code),
                    confidence=0.6,
                    source="database"
                )
        
        return None
    
    def map_condition_to_icd10(self, condition_text: str) -> MappingResult:
        """
        Map a condition description to ICD-10 code with confidence.
        Uses hybrid approach: database → semantic → ML classifier.
        """
        condition_lower = condition_text.lower().strip()
        
        # Step 1: Try exact database lookup
        if condition_lower in self.condition_map:
            codes = self.condition_map[condition_lower]
            if codes:
                code = codes[0]
                return MappingResult(
                    code=code,
                    description=self.get_icd10_description(code),
                    hcc=self.get_hcc_from_icd10(code),
                    confidence=0.95,
                    source="database"
                )
        
        # Step 2: Find candidate codes
        candidates = self.find_icd10_by_condition(condition_text)
        
        if not candidates:
            return None
        
        # Step 3: If single candidate, return it
        if len(candidates) == 1:
            return candidates[0]
        
        # Step 4: Use ML classifier if multiple candidates
        candidate_codes = [c.code for c in candidates]
        ml_result = self.classify_ambiguous_code(condition_text, candidate_codes)
        
        if ml_result:
            return ml_result
        
        # Fall back to highest confidence
        return sorted(candidates, key=lambda c: c.confidence, reverse=True)[0]
    
    def validate_code_sequence(self, codes: List[str]) -> Dict:
        """Validate a sequence of ICD-10 codes"""
        validation = {
            "valid_codes": [],
            "invalid_codes": [],
            "warnings": [],
            "total": len(codes),
            "valid_count": 0
        }
        
        for code in codes:
            is_valid, msg = self.validate_icd10_code(code)
            if is_valid:
                validation["valid_codes"].append(code.upper())
                validation["valid_count"] += 1
            else:
                validation["invalid_codes"].append({"code": code, "error": msg})
        
        return validation
    
    def get_code_alternatives(self, code: str) -> List[Dict]:
        """Get alternative ICD-10 codes with similar HCC"""
        code_upper = code.upper()
        hcc = self.get_hcc_from_icd10(code_upper)
        
        if not hcc:
            return []
        
        alternatives = []
        for db_code, details in self.codes_db.items():
            if details.get("hcc") == hcc and db_code != code_upper:
                alternatives.append({
                    "code": db_code,
                    "description": details["description"],
                    "hcc": hcc
                })
        
        return alternatives[:5]


# Module-level singleton
_mapper_instance = None

def get_icd10_mapper() -> EnhancedICD10Mapper:
    """Get or create the ICD-10 mapper singleton"""
    global _mapper_instance
    if _mapper_instance is None:
        _mapper_instance = EnhancedICD10Mapper()
    return _mapper_instance


# Backward compatibility functions
def validate_icd10_code(code: str) -> Tuple[bool, str]:
    """Validate ICD-10 code (backward compatible)"""
    mapper = get_icd10_mapper()
    return mapper.validate_icd10_code(code)


def get_icd10_description(code: str) -> str:
    """Get ICD-10 description (backward compatible)"""
    mapper = get_icd10_mapper()
    return mapper.get_icd10_description(code)


def get_hcc_from_icd10(code: str) -> Optional[str]:
    """Get HCC from ICD-10 code (backward compatible)"""
    mapper = get_icd10_mapper()
    return mapper.get_hcc_from_icd10(code)


def find_icd10_by_condition(condition: str) -> List[Dict]:
    """Find ICD-10 codes by condition (backward compatible)"""
    mapper = get_icd10_mapper()
    results = mapper.find_icd10_by_condition(condition)
    return [r.to_dict() for r in results]


def validate_code_sequence(codes: List[str]) -> Dict:
    """Validate code sequence (backward compatible)"""
    mapper = get_icd10_mapper()
    return mapper.validate_code_sequence(codes)
