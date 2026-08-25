"""
LLM Integration Layer for Enhanced Clinical Reasoning
Supports OpenAI, Anthropic, and local models (Ollama, LM Studio)
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_used: int = 0
    confidence: float = 0.9


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def complete(self, prompt: str, system_prompt: str = "", **kwargs) -> LLMResponse:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4, GPT-3.5)"""

    def __init__(self, api_key: str = None, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import openai
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=self.api_key)
        return self._client

    def complete(self, prompt: str, system_prompt: str = "", **kwargs) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("OpenAI not available. Set OPENAI_API_KEY and install openai package.")

        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )


class AnthropicProvider(LLMProvider):
    """Anthropic API provider (Claude)"""

    def __init__(self, api_key: str = None, model: str = "claude-3-opus-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import anthropic
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def complete(self, prompt: str, system_prompt: str = "", **kwargs) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("Anthropic not available. Set ANTHROPIC_API_KEY and install anthropic package.")

        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2000),
        )

        return LLMResponse(
            content=response.content[0].text,
            model=self.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )


class LocalLLMProvider(LLMProvider):
    """Local LLM provider (Ollama, LM Studio, etc.)"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3:8b"):
        self.base_url = base_url
        self.model = model
        self._session = None

    def is_available(self) -> bool:
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def complete(self, prompt: str, system_prompt: str = "", **kwargs) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError(f"Local LLM not available at {self.base_url}. Start Ollama or LM Studio.")

        import requests

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.3),
                    "num_predict": kwargs.get("max_tokens", 2000),
                },
            },
            timeout=kwargs.get("timeout", 120),
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data.get("response", ""),
            model=self.model,
            tokens_used=0,
        )


class MockLLMProvider(LLMProvider):
    """Mock provider for testing without API keys"""

    def is_available(self) -> bool:
        return True

    def complete(self, prompt: str, system_prompt: str = "", **kwargs) -> LLMResponse:
        return LLMResponse(
            content="[MOCK LLM RESPONSE] Enhanced clinical analysis would be generated here with a real LLM.",
            model="mock",
        )


class LLMManager:
    """Manages multiple LLM providers with fallback"""

    def __init__(self):
        self.providers: List[LLMProvider] = []
        self._initialize_providers()

    def _initialize_providers(self):
        # Order of preference: OpenAI -> Anthropic -> Local -> Mock
        self.providers = [
            OpenAIProvider(),
            AnthropicProvider(),
            LocalLLMProvider(),
            MockLLMProvider(),
        ]

    def get_provider(self) -> Optional[LLMProvider]:
        for provider in self.providers:
            if provider.is_available():
                logger.info(f"Using LLM provider: {provider.__class__.__name__}")
                return provider
        return MockLLMProvider()

    def complete(self, prompt: str, system_prompt: str = "", **kwargs) -> LLMResponse:
        provider = self.get_provider()
        return provider.complete(prompt, system_prompt, **kwargs)


# Singleton instance
_llm_manager = None


def get_llm_manager() -> LLMManager:
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager


# Clinical System Prompts
CLINICAL_SYSTEM_PROMPTS = {
    "hcc_analysis": """You are a certified medical coder and clinical documentation specialist with expertise in CMS-HCC risk adjustment coding.
Analyze the provided medical documentation and:
1. Identify all documented diagnoses with clinical evidence
2. Map to appropriate ICD-10-CM codes with specificity
3. Determine applicable HCC codes per CMS 2025 guidelines
4. Identify hierarchy conflicts and code exclusions
5. Provide RAF score contributions for each HCC
6. Flag documentation gaps affecting risk adjustment
7. Suggest queries for clinical documentation improvement (CDI)

Format your response as structured JSON with: conditions, icd10_codes, hcc_codes, hierarchy_issues, raf_contributions, documentation_gaps, cdi_queries.""",

    "code_suggestion": """You are an AI coding assistant for medical coders. Based on the clinical text provided, suggest:
1. Additional ICD-10-CM codes that should be considered
2. More specific code alternatives (e.g., with complications vs without)
3. Missing HCC codes based on clinical evidence
4. Coding guideline references (AHA Coding Clinic, CMS guidelines)

Return as JSON with: suggested_codes, rationale, guideline_references, confidence.""",

    "documentation_generation": """You are a clinical documentation specialist. Generate a comprehensive coding summary report including:
1. Patient clinical summary
2. HCC capture analysis
3. Risk score calculation
4. Quality metrics (specificity, completeness, accuracy)
5. Audit risk assessment
6. Recommendations for documentation improvement

Format as professional medical coding report.""",

    "audit_support": """You are a compliance auditor. Review the coding decisions and provide:
1. Compliance assessment per CMS guidelines
2. Audit risk level (Low/Medium/High)
3. Specific vulnerabilities
4. Corrective action recommendations
5. Supporting regulatory references

Return as JSON with: compliance_score, risk_level, vulnerabilities, recommendations, references.""",
}


def analyze_with_llm(
    clinical_text: str,
    nlp_entities: Dict,
    analysis_type: str = "hcc_analysis",
    patient_context: Dict = None,
) -> Dict:
    """
    Enhanced clinical analysis using LLM.

    Args:
        clinical_text: Raw OCR text from medical document
        nlp_entities: Entities extracted by biomedical NLP
        analysis_type: Type of analysis (hcc_analysis, code_suggestion, documentation_generation, audit_support)
        patient_context: Optional patient demographics (age, gender, insurance_model)

    Returns:
        Structured analysis results
    """
    manager = get_llm_manager()

    system_prompt = CLINICAL_SYSTEM_PROMPTS.get(analysis_type, CLINICAL_SYSTEM_PROMPTS["hcc_analysis"])

    # Build comprehensive prompt with context
    prompt_parts = [
        f"CLINICAL DOCUMENT TEXT:\n{clinical_text[:8000]}\n",
        f"EXTRACTED NLP ENTITIES:\n{json.dumps(nlp_entities, indent=2)}\n",
    ]

    if patient_context:
        prompt_parts.append(f"PATIENT CONTEXT:\n{json.dumps(patient_context, indent=2)}\n")

    prompt = "\n".join(prompt_parts)

    try:
        response = manager.complete(prompt, system_prompt, temperature=0.2, max_tokens=3000)

        # Try to parse JSON response
        try:
            result = json.loads(response.content)
            result["_llm_metadata"] = {
                "model": response.model,
                "tokens_used": response.tokens_used,
                "analysis_type": analysis_type,
            }
            return result
        except json.JSONDecodeError:
            # Return structured fallback if JSON parsing fails
            return {
                "raw_response": response.content,
                "_llm_metadata": {
                    "model": response.model,
                    "tokens_used": response.tokens_used,
                    "analysis_type": analysis_type,
                    "parse_error": "Response not valid JSON",
                },
            }

    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        return {
            "error": str(e),
            "_llm_metadata": {
                "analysis_type": analysis_type,
                "error": True,
            },
        }


def generate_coding_summary(
    clinical_text: str,
    nlp_entities: Dict,
    icd10_codes: List[str],
    hcc_codes: List[Dict],
    raf_score: float,
    patient_data: Dict,
) -> str:
    """Generate professional coding summary report using LLM"""
    manager = get_llm_manager()

    prompt = f"""Generate a professional HCC Coding Summary Report.

PATIENT: {patient_data.get('patient_id', 'N/A')}, Age: {patient_data.get('age', 'N/A')}, Gender: {patient_data.get('gender', 'N/A')}, Model: {patient_data.get('insurance_model', 'MA')}

CLINICAL TEXT: {clinical_text[:5000]}

IDENTIFIED CONDITIONS: {[c.get('text') if isinstance(c, dict) else c for c in nlp_entities.get('entities', {}).get('conditions', [])]}

ICD-10 CODES: {icd10_codes}

HCC CODES: {[h.get('hcc_code') if isinstance(h, dict) else h for h in hcc_codes]}

RAF SCORE: {raf_score}

Create a structured report with:
1. Executive Summary
2. Clinical Findings
3. HCC Capture Analysis
4. Risk Adjustment Calculation
5. Compliance & Audit Assessment
6. Recommendations"""

    response = manager.complete(prompt, CLINICAL_SYSTEM_PROMPTS["documentation_generation"], temperature=0.3)
    return response.content


def suggest_additional_codes(
    clinical_text: str,
    current_icd10: List[str],
    current_hcc: List[str],
    nlp_entities: Dict,
) -> Dict:
    """Get AI-powered code suggestions"""
    return analyze_with_llm(
        clinical_text,
        nlp_entities,
        analysis_type="code_suggestion",
    )


def assess_audit_risk(
    clinical_text: str,
    coded_icd10: List[str],
    coded_hcc: List[str],
    nlp_entities: Dict,
) -> Dict:
    """Assess audit risk for coded claims"""
    return analyze_with_llm(
        clinical_text,
        nlp_entities,
        analysis_type="audit_support",
    )