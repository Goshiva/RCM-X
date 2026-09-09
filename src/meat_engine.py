"""
Clinical Evidence & MEAT Criteria Engine
Comprehensive validation and evidence extraction for HCC Risk Adjustment Coding.
Supports CMS RADV audit requirements by verifying Monitor, Evaluate, Assess, Treat (MEAT) criteria,
classifying clinical document sections, and linking condition-specific medications and labs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Set


# ==============================================================================
# Clinical Section Definitions & Weights
# ==============================================================================

class SectionType:
    ASSESSMENT_AND_PLAN = "ASSESSMENT_AND_PLAN"
    HPI = "HPI"
    MEDICATIONS = "MEDICATIONS"
    PHYSICAL_EXAM = "PHYSICAL_EXAM"
    LABS_AND_DIAGNOSTICS = "LABS_AND_DIAGNOSTICS"
    PAST_MEDICAL_HISTORY = "PAST_MEDICAL_HISTORY"
    FAMILY_SOCIAL_HISTORY = "FAMILY_SOCIAL_HISTORY"
    GENERAL = "GENERAL"


# Section weights for CMS RADV audit substantiation
SECTION_AUDIT_WEIGHTS: Dict[str, str] = {
    SectionType.ASSESSMENT_AND_PLAN: "HIGH",       # Primary proof of active clinical decision making
    SectionType.HPI: "HIGH",                       # Documented active reason for encounter / interval history
    SectionType.MEDICATIONS: "HIGH",               # Active treatment plan / orders
    SectionType.PHYSICAL_EXAM: "MEDIUM",           # Examination evidence
    SectionType.LABS_AND_DIAGNOSTICS: "MEDIUM",     # Diagnostic evaluation
    SectionType.PAST_MEDICAL_HISTORY: "LOW",       # Disallowed by RADV if sole documentation
    SectionType.FAMILY_SOCIAL_HISTORY: "EXCLUDED", # Disallowed (not patient active disease)
    SectionType.GENERAL: "MEDIUM",
}


@dataclass
class ClinicalSection:
    section_type: str
    header: str
    content: str
    page_number: int
    start_char: int
    end_char: int
    audit_weight: str


# ==============================================================================
# MEAT Evidence Data Structures
# ==============================================================================

@dataclass
class MEATCriterionEvidence:
    criterion: str              # "M", "E", "A", "T"
    criterion_name: str         # "Monitor", "Evaluate", "Assess", "Treat"
    present: bool = False
    evidence_text: str = ""
    page_number: int = 1
    section_type: str = SectionType.GENERAL
    audit_weight: str = "MEDIUM"
    confidence: float = 0.0
    matched_term: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditGrade:
    AUDIT_PROOF = "AUDIT_PROOF"             # 2+ MEAT criteria in high-weight section
    SUPPORTED = "SUPPORTED"                 # 1 strong MEAT criterion in active section
    PMH_ONLY_AT_RISK = "PMH_ONLY_AT_RISK"   # Condition found only in PMH/Problem List (RADV Risk!)
    QUERY_OPPORTUNITY = "QUERY_OPPORTUNITY" # Lab/medication present but diagnosis unconfirmed
    NEGATED = "NEGATED"                     # Condition ruled out or negated


@dataclass
class ConditionMEATAnalysis:
    condition_name: str
    canonical_condition: str
    icd10_suggestions: List[str] = field(default_factory=list)
    audit_grade: str = AuditGrade.PMH_ONLY_AT_RISK
    audit_grade_label: str = "At Risk: PMH Only"
    meat_score: int = 0                     # Number of satisfied criteria (0 - 4)
    is_negated: bool = False
    is_pmh_only: bool = False
    criteria: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    all_evidence: List[Dict[str, Any]] = field(default_factory=list)
    query_opportunity: Optional[str] = None
    overall_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Clinical Knowledge Base & Ontology
# ==============================================================================

CLINICAL_ONTOLOGY: Dict[str, Dict[str, Any]] = {
    "diabetes": {
        "canonical": "Type 2 Diabetes Mellitus",
        "synonyms": [
            "diabetes", "diabetes mellitus", "t2dm", "dm2", "type 2 dm",
            "type ii diabetes", "diabetic", "hyperglycemia"
        ],
        "default_icd10": ["E11.9", "E11.22", "E11.40", "E11.69"],
        "medications": [
            "metformin", "glucophage", "glipizide", "glimepiride", "glyburide",
            "insulin", "lantus", "humalog", "novolog", "tresiba", "levemir",
            "jardiance", "empagliflozin", "farxiga", "dapagliflozin", "invokana",
            "januvia", "sitagliptin", "tradjenta", "linagliptin", "ozempic",
            "semaglutide", "victoza", "liraglutide", "trulicity", "dulaglutide",
            "mounjaro", "tirzepatide", "pioglitazone", "actos"
        ],
        "labs_diagnostics": [
            "hba1c", "a1c", "hemoglobin a1c", "glycated hemoglobin", "blood glucose",
            "fasting glucose", "fingerstick", "microalbumin", "urine albumin", "uacr"
        ],
        "exam_symptoms": [
            "polyuria", "polydipsia", "diabetic neuropathy", "tingling in feet",
            "diabetic retinopathy", "foot ulcer", "monofilament"
        ],
        "query_criteria": "eGFR < 60 with Diabetes suggests Diabetic Chronic Kidney Disease (E11.22)"
    },
    "heart_failure": {
        "canonical": "Congestive Heart Failure",
        "synonyms": [
            "heart failure", "chf", "congestive heart failure", "cardiac failure",
            "systolic heart failure", "diastolic heart failure", "hfref", "hfpef",
            "cardiomyopathy", "decompensated heart failure"
        ],
        "default_icd10": ["I50.9", "I50.22", "I50.32", "I50.42"],
        "medications": [
            "furosemide", "lasix", "spironolactone", "aldactone", "entresto",
            "sacubitril", "carvedilol", "coreg", "metoprolol succinate", "toprol",
            "bumex", "bumetanide", "torsemide", "demadex", "digoxin", "lanoxin",
            "eplerenone", "hydralazine", "isordil"
        ],
        "labs_diagnostics": [
            "bnp", "nt-probnp", "brain natriuretic peptide", "ejection fraction", "ef",
            "echocardiogram", "echo", "chest x-ray", "cxr", "cardiomegaly"
        ],
        "exam_symptoms": [
            "edema", "pedal edema", "peripheral edema", "rales", "crackles",
            "jvd", "jugular venous distention", "s3 gallop", "orthopnea", "pnd",
            "dyspnea on exertion", "shortness of breath"
        ],
        "query_criteria": "Specify Heart Failure type: Systolic (HFrEF), Diastolic (HFpEF), or Combined"
    },
    "chronic_kidney_disease": {
        "canonical": "Chronic Kidney Disease",
        "synonyms": [
            "chronic kidney disease", "ckd", "renal insufficiency", "renal failure",
            "chronic renal failure", "crf", "end stage renal disease", "esrd",
            "nephropathy"
        ],
        "default_icd10": ["N18.3", "N18.4", "N18.5", "N18.6", "N18.9"],
        "medications": [
            "lisinopril", "losartan", "calcium acetate", "phoslo", "sevelamer",
            "renvela", "rocaltrol", "calcitriol", "darbepoetin", "aranesp",
            "procrit", "epogen", "sodium bicarbonate"
        ],
        "labs_diagnostics": [
            "egfr", "gfr", "serum creatinine", "creatinine", "bun", "proteinuria",
            "microalbuminuria", "renal ultrasound", "kidney biopsy"
        ],
        "exam_symptoms": [
            "uremia", "fluid overload", "oliguria", "fistula", "dialysis catheter"
        ],
        "query_criteria": "eGFR 30-59 indicates CKD Stage 3 (N18.3); eGFR 15-29 indicates CKD Stage 4 (N18.4)"
    },
    "copd": {
        "canonical": "Chronic Obstructive Pulmonary Disease",
        "synonyms": [
            "copd", "chronic obstructive pulmonary disease", "emphysema",
            "chronic bronchitis", "chronic airway obstruction"
        ],
        "default_icd10": ["J44.9", "J44.0", "J44.1"],
        "medications": [
            "albuterol", "ventolin", "proair", "combivent", "duoneb",
            "ipratropium", "atrovent", "tiotropium", "spiriva", "advair",
            "fluticasone", "symbicort", "budesonide", "trelegy", "breo",
            "anoro", "incruse", "prednisone", "theophylline"
        ],
        "labs_diagnostics": [
            "spirometry", "pft", "pulmonary function test", "fev1", "fvc",
            "pulse oximetry", "o2 saturation", "chest ct", "abg"
        ],
        "exam_symptoms": [
            "wheezing", "rhonchi", "decreased breath sounds", "barrel chest",
            "prolonged expiratory phase", "chronic cough", "sputum production"
        ],
        "query_criteria": "Specify COPD with acute exacerbation (J44.1) or acute lower respiratory infection (J44.0) if present"
    },
    "morbid_obesity": {
        "canonical": "Morbid Obesity",
        "synonyms": [
            "morbid obesity", "severe obesity", "class 3 obesity", "class iii obesity",
            "extreme obesity", "clinically severe obesity"
        ],
        "default_icd10": ["E66.01", "Z68.41", "Z68.42", "Z68.43", "Z68.44"],
        "medications": [
            "wegovy", "zepbound", "saxenda", "phentermine", "qsymia",
            "contrave", "orlistat"
        ],
        "labs_diagnostics": [
            "bmi", "body mass index", "weight"
        ],
        "exam_symptoms": [
            "obese habitus", "excessive adiposity"
        ],
        "query_criteria": "BMI >= 40.0, or BMI >= 35.0 with serious comorbidity justifies coding Morbid Obesity (E66.01)"
    },
    "hypertension": {
        "canonical": "Essential Hypertension",
        "synonyms": [
            "hypertension", "htn", "high blood pressure", "essential hypertension"
        ],
        "default_icd10": ["I10"],
        "medications": [
            "lisinopril", "amlodipine", "losartan", "hydrochlorothiazide", "hctz",
            "atenolol", "metoprolol", "valsartan", "chlorthalidone"
        ],
        "labs_diagnostics": [
            "blood pressure", "bp", "basic metabolic panel"
        ],
        "exam_symptoms": [
            "elevated bp", "hypertensive reading"
        ],
        "query_criteria": "If patient has CKD or Heart Failure, code Hypertensive CKD (I12) or Hypertensive Heart Disease (I11)"
    },
    "atrial_fibrillation": {
        "canonical": "Atrial Fibrillation",
        "synonyms": [
            "atrial fibrillation", "a-fib", "afib", "atrial flutter", "a-flutter"
        ],
        "default_icd10": ["I48.0", "I48.1", "I48.2", "I48.91"],
        "medications": [
            "eliquis", "apixaban", "xarelto", "rivaroxaban", "warfarin", "coumadin",
            "pradaxa", "dabigatran", "amiodarone", "diltiazem", "metoprolol"
        ],
        "labs_diagnostics": [
            "ecg", "ekg", "holter monitor", "inr", "pt/inr"
        ],
        "exam_symptoms": [
            "irregularly irregular rhythm", "palpitations", "tachycardia"
        ],
        "query_criteria": "Specify Paroxysmal (I48.0), Persistent (I48.1), or Chronic/Permanent (I48.2) Atrial Fibrillation"
    },
    "depression": {
        "canonical": "Major Depressive Disorder",
        "synonyms": [
            "major depression", "mdd", "depressive disorder", "bipolar", "depression"
        ],
        "default_icd10": ["F32.9", "F33.0", "F33.1", "F33.2"],
        "medications": [
            "sertraline", "zoloft", "fluoxetine", "prozac", "escitalopram", "lexapro",
            "citalopram", "duloxetine", "cymbalta", "venlafaxine", "effexor",
            "bupropion", "wellbutrin", "mirtazapine", "remeron"
        ],
        "labs_diagnostics": [
            "phq-9", "phq-2", "psychiatric evaluation", "depression screening"
        ],
        "exam_symptoms": [
            "depressed mood", "anhedonia", "flat affect", "fatigue", "insomnia"
        ],
        "query_criteria": "Specify single episode (F32) vs recurrent (F33) and current severity (mild, moderate, severe)"
    }
}


# ==============================================================================
# Action Verb Patterns for M, E, A, T
# ==============================================================================

MEAT_ACTION_PATTERNS = {
    "Monitor": re.compile(
        r"\b(?:monitor(?:ing|ed)?|follow[- ]?up|f/u|recheck|trend(?:ing)?|stable|"
        r"worsening|improving|controlled|uncontrolled|surveillance|track(?:ing)?|"
        r"compensated|decompensated|baseline|frequency|exacerbation)\b",
        re.IGNORECASE
    ),
    "Evaluate": re.compile(
        r"\b(?:evaluat(?:e|ed|ing|ion)|reviewed?|review\s+of|ordered?|test\s+results?|"
        r"lab(?:oratory)?|imaging|ultrasound|echo(?:cardiogram)?|ecg|ekg|chest\s+x[- ]?ray|"
        r"cxr|consult(?:ation)?|referred\s+to|referral|biopsy|panel|screen(?:ing|ed)?|"
        r"noted|revealed|discussed\s+with\s+specialist)\b",
        re.IGNORECASE
    ),
    "Assess": re.compile(
        r"\b(?:assess(?:ment|ed|ing)?|diagnos(?:is|ed|ing)?|impression|severity|"
        r"stage|class|counsel(?:ed|ing)?|education\s+provided|prognosis|status:|"
        r"differential|chronic|persistent|etiology|confirmed)\b",
        re.IGNORECASE
    ),
    "Treat": re.compile(
        r"\b(?:continue[ds]?|prescrib(?:e|ed|ing)|refill(?:ed|s)?|started\s+on|"
        r"initiat(?:e|ed|ing)|titrat(?:e|ed|ing)|dose\s+(?:adjusted|increased|decreased)|"
        r"administ(?:er|ered)|treatment|therap(?:y|ies)|regimen|lifestyle\s+modifications?|"
        r"diet|restriction|cardiac\s+rehab|wound\s+care|dialysis|surgery|order(?:ed)?)\b",
        re.IGNORECASE
    ),
}


# ==============================================================================
# Negation & Family History Detector
# ==============================================================================

class NegationDetector:
    """Detects negated findings and family history mentions to suppress false positives."""

    NEGATION_TRIGGERS = re.compile(
        r"\b(?:no\s+(?:evidence|signs?|symptoms?|history)\s+of|"
        r"denies|negative\s+for|rules?\s+out|ruled\s+out|unlikely|"
        r"without|free\s+of|non[- ]contributory|resolved|no\s+complaints\s+of)\b",
        re.IGNORECASE
    )

    FAMILY_HISTORY_TRIGGERS = re.compile(
        r"\b(?:mother|father|sister|brother|parent|maternal|paternal|family\s+history|fhx?)\b",
        re.IGNORECASE
    )

    @classmethod
    def is_negated(cls, sentence: str, term: str) -> bool:
        """Check if term appears in a negated context within the sentence."""
        term_idx = sentence.lower().find(term.lower())
        if term_idx == -1:
            return False

        # Look back up to 60 characters before the term
        pre_context = sentence[max(0, term_idx - 60):term_idx]
        if cls.NEGATION_TRIGGERS.search(pre_context):
            return True

        # Look ahead up to 40 characters after the term (e.g., "was ruled out", "is negative")
        post_context = sentence[term_idx:min(len(sentence), term_idx + len(term) + 40)]
        if re.search(r"\b(?:ruled\s+out|is\s+negative|unlikely|resolved)\b", post_context, re.IGNORECASE):
            return True

        return False

    @classmethod
    def is_family_history(cls, sentence: str, section_type: str) -> bool:
        """Check if sentence refers to family history rather than the patient."""
        if section_type == SectionType.FAMILY_SOCIAL_HISTORY:
            return True
        return bool(cls.FAMILY_HISTORY_TRIGGERS.search(sentence))


# ==============================================================================
# Clinical Section Parser
# ==============================================================================

class ClinicalSectionParser:
    """Segments clinical documentation into structured clinical sections with audit weights."""

    SECTION_HEADER_PATTERNS: List[Tuple[str, re.Pattern]] = [
        (
            SectionType.ASSESSMENT_AND_PLAN,
            re.compile(
                r"^(?:#+\s*)?(?:assessment\s*(?:and|&)\s*plan|a\s*/\s*p|impression\s*(?:and|&)\s*plan|"
                r"assessment|impression|plan|recommendations?)\s*:?$",
                re.IGNORECASE
            )
        ),
        (
            SectionType.HPI,
            re.compile(
                r"^(?:#+\s*)?(?:history\s+of\s+present\s+illness|hpi|subjective|interval\s+history|"
                r"chief\s+complaint|reason\s+for\s+visit)\s*:?$",
                re.IGNORECASE
            )
        ),
        (
            SectionType.MEDICATIONS,
            re.compile(
                r"^(?:#+\s*)?(?:current\s+medications?|active\s+medications?|medication\s+list|"
                r"medications?|prescriptions?|orders?)\s*:?$",
                re.IGNORECASE
            )
        ),
        (
            SectionType.PHYSICAL_EXAM,
            re.compile(
                r"^(?:#+\s*)?(?:physical\s+examination|physical\s+exam|pe\b|objective|"
                r"exam|vital\s+signs?|vitals?)\s*:?$",
                re.IGNORECASE
            )
        ),
        (
            SectionType.LABS_AND_DIAGNOSTICS,
            re.compile(
                r"^(?:#+\s*)?(?:laboratory\s*(?:and|&)\s*diagnostic\s*data|laboratory\s+(?:data|results?)|"
                r"diagnostic\s+(?:data|results?)|labs?|imaging|diagnostic\s+studies?)\s*:?$",
                re.IGNORECASE
            )
        ),
        (
            SectionType.PAST_MEDICAL_HISTORY,
            re.compile(
                r"^(?:#+\s*)?(?:past\s+medical\s+history|pmh|past\s+history|medical\s+history|"
                r"problem\s+list|active\s+problems?)\s*:?$",
                re.IGNORECASE
            )
        ),
        (
            SectionType.FAMILY_SOCIAL_HISTORY,
            re.compile(
                r"^(?:#+\s*)?(?:family\s+(?:medical\s+)?history|social\s+history|fhx?|shx?)\s*:?$",
                re.IGNORECASE
            )
        ),
    ]

    @classmethod
    def parse_document(cls, text: str, pages: Optional[List[str]] = None) -> List[ClinicalSection]:
        """
        Parse raw text into tagged clinical sections with page attribution.
        """
        source_pages = pages if pages and len(pages) > 0 else [text]
        sections: List[ClinicalSection] = []

        global_offset = 0
        for page_idx, page_text in enumerate(source_pages, start=1):
            lines = page_text.splitlines(keepends=True)
            current_section_type = SectionType.GENERAL
            current_header = "General Note"
            current_lines: List[str] = []
            section_start_char = global_offset

            for line in lines:
                trimmed = line.strip()
                matched_section: Optional[Tuple[str, str]] = None

                # Check if this line is a section header
                if trimmed and len(trimmed) < 60:
                    for s_type, pattern in cls.SECTION_HEADER_PATTERNS:
                        if pattern.match(trimmed):
                            matched_section = (s_type, trimmed)
                            break

                if matched_section:
                    # Flush previous section if it has content
                    if current_lines:
                        content_str = "".join(current_lines).strip()
                        if content_str:
                            sections.append(ClinicalSection(
                                section_type=current_section_type,
                                header=current_header,
                                content=content_str,
                                page_number=page_idx,
                                start_char=section_start_char,
                                end_char=section_start_char + len("".join(current_lines)),
                                audit_weight=SECTION_AUDIT_WEIGHTS.get(current_section_type, "MEDIUM")
                            ))
                    # Begin new section
                    current_section_type, current_header = matched_section
                    current_lines = []
                    section_start_char = global_offset
                else:
                    current_lines.append(line)

                global_offset += len(line)

            # Flush final section on page
            if current_lines:
                content_str = "".join(current_lines).strip()
                if content_str:
                    sections.append(ClinicalSection(
                        section_type=current_section_type,
                        header=current_header,
                        content=content_str,
                        page_number=page_idx,
                        start_char=section_start_char,
                        end_char=section_start_char + len("".join(current_lines)),
                        audit_weight=SECTION_AUDIT_WEIGHTS.get(current_section_type, "MEDIUM")
                    ))

        if not sections:
            # Fallback if no explicit headers found
            sections.append(ClinicalSection(
                section_type=SectionType.GENERAL,
                header="General Encounter",
                content=text,
                page_number=1,
                start_char=0,
                end_char=len(text),
                audit_weight="MEDIUM"
            ))

        return sections


# ==============================================================================
# MEAT Criteria Engine
# ==============================================================================

class MEATEngine:
    """
    Core engine evaluating clinical documentation against CMS-HCC MEAT criteria.
    Links condition-specific medications, labs, signs, and section weights.
    """

    def __init__(self, custom_ontology: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.ontology = custom_ontology or CLINICAL_ONTOLOGY

    def split_sentences(self, text: str) -> List[str]:
        """Split text into sentences while preserving meaningful clinical boundaries."""
        raw_sentences = re.split(r"(?<=[.!?\n])\s+(?=[A-Z0-9\-\*•])", text)
        sentences = []
        for s in raw_sentences:
            s_clean = s.strip()
            if s_clean and len(s_clean) > 8:
                sentences.append(s_clean)
        return sentences

    def match_condition_key(self, condition_name: str) -> Optional[str]:
        """Find ontology key corresponding to a diagnosed condition name."""
        clean_name = condition_name.lower().strip()
        for key, data in self.ontology.items():
            if clean_name == key or clean_name in data["synonyms"]:
                return key
            for syn in data["synonyms"]:
                if syn in clean_name or clean_name in syn:
                    return key
        return None

    def evaluate_condition(
        self,
        condition_name: str,
        sections: List[ClinicalSection],
        icd10_codes: Optional[List[str]] = None
    ) -> ConditionMEATAnalysis:
        """
        Comprehensive MEAT evaluation for a single candidate medical condition.
        """
        ontology_key = self.match_condition_key(condition_name)
        onto_data = self.ontology.get(ontology_key) if ontology_key else None
        canonical_name = onto_data["canonical"] if onto_data else condition_name.title()
        suggested_icd10 = list(icd10_codes or (onto_data["default_icd10"] if onto_data else []))

        # Condition search terms
        search_terms: List[str] = [condition_name.lower()]
        if onto_data:
            search_terms.extend([syn.lower() for syn in onto_data["synonyms"]])

        # Condition-specific linked entities
        specific_meds: Set[str] = set(onto_data["medications"]) if onto_data else set()
        specific_labs: Set[str] = set(onto_data["labs_diagnostics"]) if onto_data else set()
        specific_symptoms: Set[str] = set(onto_data["exam_symptoms"]) if onto_data else set()

        # Track evidence by criterion
        evidence_by_criterion: Dict[str, List[MEATCriterionEvidence]] = {
            "M": [], "E": [], "A": [], "T": []
        }

        found_in_active_section = False
        found_in_pmh = False
        condition_negated = False

        for section in sections:
            if section.section_type == SectionType.FAMILY_SOCIAL_HISTORY:
                continue

            sentences = self.split_sentences(section.content)
            for sentence in sentences:
                sentence_lower = sentence.lower()

                # Check if condition is mentioned in this sentence
                has_condition = any(term in sentence_lower for term in search_terms)

                # Check for linked medication mention even without explicit condition name
                has_linked_med = any(
                    re.search(rf"\b{re.escape(med)}\b", sentence_lower)
                    for med in specific_meds
                )
                # Check for linked lab mention
                has_linked_lab = any(
                    re.search(rf"\b{re.escape(lab)}\b", sentence_lower)
                    for lab in specific_labs
                )

                if not (has_condition or has_linked_med or has_linked_lab):
                    continue

                # Check family history
                if NegationDetector.is_family_history(sentence, section.section_type):
                    continue

                # Check negation
                if has_condition and NegationDetector.is_negated(sentence, condition_name):
                    condition_negated = True
                    continue

                # Section tracking
                if section.section_type == SectionType.PAST_MEDICAL_HISTORY:
                    if has_condition:
                        found_in_pmh = True
                    # PMH does not qualify as active MEAT for this encounter
                    continue

                found_in_active_section = True

                # Evaluate Treat (T)
                treat_match = MEAT_ACTION_PATTERNS["Treat"].search(sentence)
                if has_linked_med or (has_condition and treat_match):
                    matched_kw = treat_match.group(0) if treat_match else "medication"
                    evidence_by_criterion["T"].append(MEATCriterionEvidence(
                        criterion="T",
                        criterion_name="Treat",
                        present=True,
                        evidence_text=sentence,
                        page_number=section.page_number,
                        section_type=section.section_type,
                        audit_weight=section.audit_weight,
                        confidence=0.90 if has_linked_med else 0.75,
                        matched_term=matched_kw
                    ))

                # Evaluate Evaluate (E)
                eval_match = MEAT_ACTION_PATTERNS["Evaluate"].search(sentence)
                if has_linked_lab or (has_condition and eval_match):
                    matched_kw = eval_match.group(0) if eval_match else "diagnostic_review"
                    evidence_by_criterion["E"].append(MEATCriterionEvidence(
                        criterion="E",
                        criterion_name="Evaluate",
                        present=True,
                        evidence_text=sentence,
                        page_number=section.page_number,
                        section_type=section.section_type,
                        audit_weight=section.audit_weight,
                        confidence=0.88 if has_linked_lab else 0.75,
                        matched_term=matched_kw
                    ))

                # Evaluate Assess (A)
                assess_match = MEAT_ACTION_PATTERNS["Assess"].search(sentence)
                is_ap_section = section.section_type == SectionType.ASSESSMENT_AND_PLAN
                if has_condition and (assess_match or is_ap_section):
                    matched_kw = assess_match.group(0) if assess_match else "Assessment & Plan"
                    evidence_by_criterion["A"].append(MEATCriterionEvidence(
                        criterion="A",
                        criterion_name="Assess",
                        present=True,
                        evidence_text=sentence,
                        page_number=section.page_number,
                        section_type=section.section_type,
                        audit_weight="HIGH" if is_ap_section else section.audit_weight,
                        confidence=0.92 if is_ap_section else 0.80,
                        matched_term=matched_kw
                    ))

                # Evaluate Monitor (M)
                monitor_match = MEAT_ACTION_PATTERNS["Monitor"].search(sentence)
                has_symptom = any(sym in sentence_lower for sym in specific_symptoms)
                if has_condition and (monitor_match or has_symptom):
                    matched_kw = monitor_match.group(0) if monitor_match else "symptom/stability"
                    evidence_by_criterion["M"].append(MEATCriterionEvidence(
                        criterion="M",
                        criterion_name="Monitor",
                        present=True,
                        evidence_text=sentence,
                        page_number=section.page_number,
                        section_type=section.section_type,
                        audit_weight=section.audit_weight,
                        confidence=0.85 if has_symptom else 0.75,
                        matched_term=matched_kw
                    ))

        # Compile criteria dictionary and select best evidence per criterion
        criteria_dict: Dict[str, Dict[str, Any]] = {}
        all_evidence_list: List[Dict[str, Any]] = []

        for crit in ["M", "E", "A", "T"]:
            crit_name = {"M": "Monitor", "E": "Evaluate", "A": "Assess", "T": "Treat"}[crit]
            ev_list = evidence_by_criterion[crit]
            if ev_list:
                # Prefer HIGH audit weight, then higher confidence
                best_ev = max(
                    ev_list,
                    key=lambda x: (1 if x.audit_weight == "HIGH" else (0.5 if x.audit_weight == "MEDIUM" else 0), x.confidence)
                )
                criteria_dict[crit] = best_ev.to_dict()
                all_evidence_list.append(best_ev.to_dict())
            else:
                criteria_dict[crit] = {
                    "criterion": crit,
                    "criterion_name": crit_name,
                    "present": False,
                    "evidence_text": "",
                    "page_number": 1,
                    "section_type": SectionType.GENERAL,
                    "audit_weight": "NONE",
                    "confidence": 0.0,
                    "matched_term": ""
                }

        meat_score = sum(1 for c in criteria_dict.values() if c.get("present"))
        is_pmh_only = found_in_pmh and not found_in_active_section

        # Determine Audit Grade
        if condition_negated and meat_score == 0:
            audit_grade = AuditGrade.NEGATED
            grade_label = "Negated / Ruled Out"
        elif is_pmh_only and meat_score == 0:
            audit_grade = AuditGrade.PMH_ONLY_AT_RISK
            grade_label = "At Risk: PMH Only"
        elif meat_score >= 2 and any(criteria_dict[k]["audit_weight"] == "HIGH" for k in ["A", "T"]):
            audit_grade = AuditGrade.AUDIT_PROOF
            grade_label = "Audit-Proof (Grade A)"
        elif meat_score >= 1:
            audit_grade = AuditGrade.SUPPORTED
            grade_label = "Supported (Grade B)"
        else:
            audit_grade = AuditGrade.PMH_ONLY_AT_RISK
            grade_label = "At Risk: Lacks MEAT"

        # Overall confidence calculation
        if meat_score >= 2:
            confidence = min(0.98, 0.70 + (meat_score * 0.07))
        elif meat_score == 1:
            confidence = 0.75
        elif is_pmh_only:
            confidence = 0.40
        else:
            confidence = 0.50

        query_opp = onto_data.get("query_criteria") if onto_data else None

        return ConditionMEATAnalysis(
            condition_name=condition_name,
            canonical_condition=canonical_name,
            icd10_suggestions=suggested_icd10,
            audit_grade=audit_grade,
            audit_grade_label=grade_label,
            meat_score=meat_score,
            is_negated=condition_negated,
            is_pmh_only=is_pmh_only,
            criteria=criteria_dict,
            all_evidence=all_evidence_list,
            query_opportunity=query_opp,
            overall_confidence=confidence
        )

    def analyze_document(
        self,
        text: str,
        pages: Optional[List[str]] = None,
        candidate_conditions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze an entire clinical document:
        1. Segments document into structured sections.
        2. Evaluates all candidate conditions against MEAT criteria.
        3. Identifies under-coding and CDI query opportunities.
        """
        sections = ClinicalSectionParser.parse_document(text, pages)

        # Detect conditions if none provided
        conditions_to_check = set(candidate_conditions or [])
        text_lower = text.lower()
        if not conditions_to_check:
            for key, data in self.ontology.items():
                if any(syn in text_lower for syn in data["synonyms"]):
                    conditions_to_check.add(data["canonical"])

        analyses: List[ConditionMEATAnalysis] = []
        for cond in sorted(conditions_to_check):
            analysis = self.evaluate_condition(cond, sections)
            analyses.append(analysis)

        # Query opportunities based on labs/meds without formal diagnoses
        query_opportunities: List[Dict[str, str]] = []
        for key, data in self.ontology.items():
            if not any(a.canonical_condition == data["canonical"] for a in analyses):
                # Condition not diagnosed, check if meds or labs are present
                has_med = any(re.search(rf"\b{re.escape(m)}\b", text_lower) for m in data["medications"])
                has_lab = any(re.search(rf"\b{re.escape(l)}\b", text_lower) for l in data["labs_diagnostics"])
                if has_med or has_lab:
                    query_opportunities.append({
                        "condition": data["canonical"],
                        "rationale": f"Clinical indicators ({'medications' if has_med else 'lab tests'}) present in note without documented diagnosis.",
                        "query_recommendation": data.get("query_criteria", "Query provider for diagnosis confirmation")
                    })

        return {
            "sections_count": len(sections),
            "analyses": [a.to_dict() for a in analyses],
            "query_opportunities": query_opportunities,
            "audit_summary": {
                "audit_proof_count": sum(1 for a in analyses if a.audit_grade == AuditGrade.AUDIT_PROOF),
                "supported_count": sum(1 for a in analyses if a.audit_grade == AuditGrade.SUPPORTED),
                "at_risk_count": sum(1 for a in analyses if a.audit_grade == AuditGrade.PMH_ONLY_AT_RISK),
                "negated_count": sum(1 for a in analyses if a.audit_grade == AuditGrade.NEGATED),
            }
        }


# Module singleton
meat_engine = MEATEngine()
