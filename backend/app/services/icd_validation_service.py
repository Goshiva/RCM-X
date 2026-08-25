from __future__ import annotations

import re
from typing import List


class ICDValidationService:
    """Simple ICD-10 validation and suggestion service for coder workflows."""

    ICD10_PATTERN = re.compile(r"^[A-TV-Z][0-9]{2,3}(?:\.[0-9A-TV-Z]{1,4})?$")
    COMMON_CODES = [
        "E11.9",
        "I10",
        "J44.9",
        "N18.9",
        "M54.5",
        "F32.9",
        "G30.9",
        "E78.5",
        "I25.10",
        "J18.9",
    ]

    def validate(self, code: str) -> bool:
        if not code:
            return False
        return bool(self.ICD10_PATTERN.fullmatch(code.strip().upper()))

    def suggest(self, partial: str) -> List[str]:
        term = partial.strip().upper()
        if not term:
            return self.COMMON_CODES[:5]

        matches = [code for code in self.COMMON_CODES if code.startswith(term)]
        if matches:
            return matches

        if len(term) >= 2:
            return [code for code in self.COMMON_CODES if term in code]
        return self.COMMON_CODES[:5]
