from __future__ import annotations

import os
import re
from typing import Dict, Any, List

from src.hcc_engine import get_hcc_from_icd10
from src.icd_mapper import ICD10Mapper
from src.icd_diagnosis_matcher import find_similar_diagnoses, lookup_diagnosis_code
from src.nlp_identifier_v3 import extract_nlp_insights
from src.ocr_module import extract_text_from_pdf
from src.meat_engine import meat_engine, ClinicalSectionParser, AuditGrade
from backend.app.core.config import CMS_MODEL_FAMILY, CMS_MODEL_VERSION
from backend.app.services.cms_model_service import cms_model_service


class NLPService:
    """Medical text extraction and ICD/HCC suggestion service."""

    ICD10_PATTERN = re.compile(r"\b[A-TV-Z][0-9]{1,3}(?:\.[0-9A-TV-Z]{1,4})?\b")

    def __init__(self) -> None:
        self.icd_mapper = ICD10Mapper()
        self.meat_engine = meat_engine

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
        entities: List[Dict[str, Any]] = []
        ents = insights["entities"].get("entities", {})
        
        # Clinical section segmentation
        sections = ClinicalSectionParser.parse_document(text, pages)

        for condition in ents.get("conditions", []):
            cond_name = condition.get("text") if isinstance(condition, dict) else condition
            suggestions = self.icd_mapper.find_icd10_by_condition(cond_name)
            workbook_matches = find_similar_diagnoses(cond_name)
            
            # Deep MEAT evaluation
            meat_analysis = self.meat_engine.evaluate_condition(
                cond_name,
                sections,
                [s.get("code") for s in suggestions if isinstance(s, dict)]
            )
            
            # Format legacy and rich evidence
            evidence_snippets = [
                {
                    "type": ev["criterion_name"],
                    "criterion": ev["criterion"],
                    "page_number": ev["page_number"],
                    "text": ev["evidence_text"],
                    "section": ev["section_type"],
                    "audit_weight": ev["audit_weight"],
                    "confidence": ev["confidence"],
                }
                for ev in meat_analysis.all_evidence
                if ev.get("present")
            ]

            entities.append({
                "type": "condition",
                "name": cond_name,
                "canonical_name": meat_analysis.canonical_condition,
                "confidence": max(meat_analysis.overall_confidence, condition.get("confidence", 0.7) if isinstance(condition, dict) else 0.7),
                "icd10_suggestions": suggestions,
                "workbook_matches": workbook_matches,
                "meat_evidence": evidence_snippets,
                "meat_criteria": meat_analysis.criteria,
                "meat_score": meat_analysis.meat_score,
                "audit_grade": meat_analysis.audit_grade,
                "audit_grade_label": meat_analysis.audit_grade_label,
                "is_negated": meat_analysis.is_negated,
                "is_pmh_only": meat_analysis.is_pmh_only,
                "query_opportunity": meat_analysis.query_opportunity,
                "meat_status": (
                    "audit_proof" if meat_analysis.audit_grade == AuditGrade.AUDIT_PROOF
                    else ("supported" if meat_analysis.audit_grade == AuditGrade.SUPPORTED
                          else ("negated" if meat_analysis.is_negated
                                else ("pmh_only" if meat_analysis.is_pmh_only else "not_found")))
                ),
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
            })

        doc_analysis = self.meat_engine.analyze_document(
            text,
            pages,
            [e["name"] for e in entities if e.get("type") == "condition"]
        )

        return {
            "text_snippet": text[:1000],
            "text": text,
            "document_type": insights["document_type"],
            "confidence": insights["confidence"],
            "medical_entities": insights["entities"],
            "entities": entities,
            "audit_summary": doc_analysis.get("audit_summary", {}),
            "query_opportunities": doc_analysis.get("query_opportunities", []),
        }

    def _find_meat_evidence(self, diagnosis: str, text: str, pages: List[str]) -> List[Dict[str, Any]]:
        """Legacy helper now powered by MEATEngine."""
        sections = ClinicalSectionParser.parse_document(text, pages)
        analysis = self.meat_engine.evaluate_condition(diagnosis, sections)
        return [
            {
                "type": ev["criterion_name"],
                "criterion": ev["criterion"],
                "page_number": ev["page_number"],
                "text": ev["evidence_text"],
                "section": ev["section_type"],
                "audit_weight": ev["audit_weight"],
            }
            for ev in analysis.all_evidence
            if ev.get("present")
        ]

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
