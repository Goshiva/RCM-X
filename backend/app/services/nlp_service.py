from __future__ import annotations

import os
import re
from typing import Dict, Any, List
from datetime import datetime

from src.hcc_engine import get_hcc_from_icd10
from src.icd_mapper import ICD10Mapper
from src.icd_diagnosis_matcher import find_similar_diagnoses, lookup_diagnosis_code
from src.nlp_identifier_v3 import extract_nlp_insights
from src.ocr_module import extract_text_from_pdf
from backend.app.core.config import CMS_MODEL_FAMILY, CMS_MODEL_VERSION
from backend.app.services.cms_model_service import cms_model_service


class NLPService:
    """Medical text extraction and ICD/HCC suggestion service."""

    ICD10_PATTERN = re.compile(r"\b[A-TV-Z][0-9]{1,3}(?:\.[0-9A-TV-Z]{1,4})?\b")
    MEAT_PATTERNS = {
        "Monitor": re.compile(r"\b(?:monitor|monitoring|follow[- ]?up|recheck|trend|stable|surveillance|track)\b", re.I),
        "Evaluate": re.compile(r"\b(?:evaluate|evaluation|exam|reviewed|result|lab|test|imaging|referral|consult)\b", re.I),
        "Assess": re.compile(r"\b(?:assess|assessment|diagnos|severity|status|counsel|discuss|differential)\w*\b", re.I),
        "Treat": re.compile(r"\b(?:treat|treatment|continue|prescri|medication|therapy|referred|surgery|dose)\w*\b", re.I),
    }
    DATE_PATTERNS = (
        re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b"),
        re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b"),
    )
    SECTION_PATTERN = re.compile(
        r"(?im)^\s*(assessment and plan|assessment|plan|impression|diagnosis|medications?|history of present illness|hpi)\s*:?\s*$"
    )

    def __init__(self) -> None:
        self.icd_mapper = ICD10Mapper()

    def extract_pdf(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return self.analyze_text("")
        text = extract_text_from_pdf(file_path)
        pages = []
        try:
            import fitz
            document = fitz.open(file_path)
            pages = [page.get_text() for page in document]
            document.close()
        except (OSError, RuntimeError):
            pages = []
        return self.analyze_text(text, pages)

    def extract_entities(self, text: str) -> Dict[str, Any]:
        return self.analyze_text(text)

    def analyze_text(self, text: str, pages: List[str] | None = None) -> Dict[str, Any]:
        insights = extract_nlp_insights(text)
        dates = self._extract_service_dates(text)
        sections = [match.group(1).lower() for match in self.SECTION_PATTERN.finditer(text)]
        entities: List[Dict[str, Any]] = []
        ents = insights["entities"].get("entities", {})
        for condition in ents.get("conditions", []):
            cond_name = condition.get("text") if isinstance(condition, dict) else condition
            suggestions = self.icd_mapper.find_icd10_by_condition(cond_name)
            workbook_matches = find_similar_diagnoses(cond_name)
            meat_evidence = self._find_meat_evidence(cond_name, text, pages or [])
            entities.append({
                "type": "condition",
                "name": cond_name,
                "confidence": condition.get("confidence", insights.get("confidence", 0.7)) if isinstance(condition, dict) else insights.get("confidence", 0.7),
                "icd10_suggestions": suggestions,
                "workbook_matches": workbook_matches,
                "meat_evidence": meat_evidence,
                "meat_status": "supported" if meat_evidence else "not_found",
                "clinical_sections": self._nearby_sections(cond_name, text, sections),
            })

        for code in sorted({m.group(0).upper() for m in self.ICD10_PATTERN.finditer(text)}):
            mapping = get_hcc_from_icd10(code)
            workbook_diagnosis = lookup_diagnosis_code(code)
            entities.append({
                "type": "icd10",
                "code": code,
                "description": workbook_diagnosis["description"] if workbook_diagnosis else self.icd_mapper.get_icd10_description(code),
                "short_description": workbook_diagnosis["short_description"] if workbook_diagnosis else None,
                "hcc": mapping,
                "confidence": 0.75,
                "evidence": self._code_evidence(code, text, pages or []),
            })

        return {
            "text_snippet": text[:1000],
            "text": text,
            "document_type": insights["document_type"],
            "confidence": insights["confidence"],
            "service_dates": dates,
            "clinical_sections": sections,
            "medical_entities": insights["entities"],
            "entities": entities,
        }

    def _extract_service_dates(self, text: str) -> List[str]:
        dates = set()
        for pattern in self.DATE_PATTERNS:
            for match in pattern.finditer(text):
                parts = [int(value) for value in match.groups()]
                year, month, day = (parts if parts[0] > 1000 else (parts[2], parts[0], parts[1]))
                try:
                    dates.add(datetime(year, month, day).date().isoformat())
                except ValueError:
                    continue
        return sorted(dates)

    def _nearby_sections(self, diagnosis: str, text: str, sections: List[str]) -> List[str]:
        lowered = text.lower()
        position = lowered.find(diagnosis.lower())
        if position < 0:
            return []
        preceding = text[:position]
        match = list(self.SECTION_PATTERN.finditer(preceding))
        return [match[-1].group(1).lower()] if match else sections[:1]

    def _code_evidence(self, code: str, text: str, pages: List[str]) -> Dict[str, Any]:
        source_pages = pages or [text]
        matches = []
        for page_number, page_text in enumerate(source_pages, start=1):
            for match in re.finditer(re.escape(code), page_text, re.I):
                start = max(0, match.start() - 90)
                end = min(len(page_text), match.end() + 140)
                matches.append({
                    "page_number": page_number,
                    "text": " ".join(page_text[start:end].split()),
                })
        return {"match_count": len(matches), "matches": matches[:5]}

    def _find_meat_evidence(self, diagnosis: str, text: str, pages: List[str]) -> List[Dict[str, Any]]:
        """Find non-blocking MEAT evidence near a detected diagnosis."""
        source_pages = pages or [text]
        evidence = []
        for page_number, page_text in enumerate(source_pages, start=1):
            diagnosis_terms = [term for term in diagnosis.lower().split() if len(term) > 3]
            if diagnosis_terms and not any(term in page_text.lower() for term in diagnosis_terms):
                continue
            for category, pattern in self.MEAT_PATTERNS.items():
                match = pattern.search(page_text)
                if match:
                    start = max(0, match.start() - 70)
                    end = min(len(page_text), match.end() + 110)
                    evidence.append({
                        "type": category,
                        "page_number": page_number,
                        "text": " ".join(page_text[start:end].split()),
                    })
        return evidence[:8]

    def suggest_hccs(
        self,
        icd10_codes: List[str],
        model_family: str = CMS_MODEL_FAMILY,
        version: str = CMS_MODEL_VERSION,
    ) -> List[Dict[str, Any]]:
        suggestions = []
        for code in icd10_codes:
            imported_mappings = cms_model_service.lookup(code, model_family, version)
            mapping = imported_mappings[0] if imported_mappings else get_hcc_from_icd10(code)
            suggestions.append({
                "icd10": code,
                "hcc": mapping,
                "model_family": model_family,
                "model_version": version,
                "description": self.icd_mapper.get_icd10_description(code),
                "confidence": 0.75 if mapping else 0.5,
            })
        return suggestions
