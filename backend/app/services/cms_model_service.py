from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class CMSMapping:
    model_family: str
    version: str
    category: str
    hcc_code: str
    hcc_name: str
    icd10_code: str
    raf_score: Optional[float] = None


@dataclass
class CMSModel:
    model_family: str
    version: str
    source_name: str
    source_sha256: str
    imported_at: datetime
    mappings: List[CMSMapping] = field(default_factory=list)

    @property
    def mapping_count(self) -> int:
        return len(self.mappings)


class CMSModelImportError(ValueError):
    """Raised when a CMS mapping file is invalid."""


class CMSModelService:
    """Versioned CMS mapping registry for imported official source files."""

    REQUIRED_COLUMNS = {
        "model_family",
        "version",
        "category",
        "hcc_code",
        "hcc_name",
        "icd10_code",
    }
    SUPPORTED = {("CMS-HCC", "V28"), ("RxHCC", "V08")}
    MODEL_METADATA = {
        ("CMS-HCC", "V28"): {
            "name": "CMS-HCC Model V28",
            "description": "CMS Medicare Advantage medical risk adjustment model version 28.",
        },
        ("RxHCC", "V08"): {
            "name": "RxHCC Model V08",
            "description": "CMS prescription-drug risk adjustment model version 8.",
        },
    }

    def __init__(self, registry_path: str = "instance/cms_models.json") -> None:
        self.registry_path = registry_path
        self._models: Dict[tuple[str, str], CMSModel] = {}
        self._load()

    def import_csv(self, content: bytes, source_name: str) -> CMSModel:
        return self.import_file(content, source_name)

    def import_file(self, content: bytes, source_name: str) -> CMSModel:
        source_sha256 = hashlib.sha256(content).hexdigest()
        rows = self._read_rows(content, source_name)
        if not rows:
            raise CMSModelImportError("CMS file contains no mappings")
        rows = [self._normalize_row(row) for row in rows]
        missing = sorted(self.REQUIRED_COLUMNS - set(rows[0]))
        if missing:
            raise CMSModelImportError(f"Missing CMS columns: {', '.join(missing)}")

        mappings: List[CMSMapping] = []
        model_keys = set()
        for row in rows:
            key = (row["model_family"].strip(), row["version"].strip())
            if key not in self.SUPPORTED:
                raise CMSModelImportError(f"Unsupported CMS model: {key[0]} {key[1]}")
            model_keys.add(key)
            try:
                raf_score = float(row["raf_score"]) if row.get("raf_score") else None
            except ValueError as exc:
                raise CMSModelImportError("raf_score must be numeric") from exc
            mappings.append(CMSMapping(
                model_family=key[0], version=key[1],
                category=row["category"].strip(), hcc_code=row["hcc_code"].strip(),
                hcc_name=row["hcc_name"].strip(), icd10_code=row["icd10_code"].strip(),
                raf_score=raf_score,
            ))

        if len(model_keys) != 1:
            raise CMSModelImportError("Each import file must contain exactly one CMS model family and version")

        model = CMSModel(
            model_family=mappings[0].model_family,
            version=mappings[0].version,
            source_name=source_name,
            source_sha256=source_sha256,
            imported_at=datetime.now(timezone.utc),
            mappings=mappings,
        )
        self._models[(model.model_family, model.version)] = model
        self._save()
        return model

    def list_models(self) -> List[CMSModel]:
        return list(self._models.values())

    def metadata(self, model_family: str, version: str) -> Optional[dict]:
        if (model_family, version) not in self.SUPPORTED:
            return None
        return {
            "model_family": model_family,
            "version": version,
            **self.MODEL_METADATA[(model_family, version)],
            "imported": (model_family, version) in self._models,
            "mapping_count": len(self._models[(model_family, version)].mappings)
            if (model_family, version) in self._models else 0,
        }

    def lookup(self, icd10_code: str, model_family: str, version: str) -> List[dict]:
        model = self._models.get((model_family, version))
        if not model:
            return []
        code = icd10_code.strip().upper()
        return [
            mapping.__dict__.copy()
            for mapping in model.mappings
            if code == mapping.icd10_code.upper() or code.startswith(mapping.icd10_code.upper())
        ]

    def categories(self, model_family: str, version: str) -> Dict[str, List[dict]]:
        model = self._models.get((model_family, version))
        if not model:
            return {}
        categories: Dict[str, List[dict]] = {}
        for mapping in model.mappings:
            categories.setdefault(mapping.category, []).append(mapping.__dict__.copy())
        return categories

    @staticmethod
    def _read_rows(content: bytes, source_name: str) -> List[dict]:
        suffix = source_name.lower().rsplit(".", 1)[-1] if "." in source_name else ""
        if suffix in {"xlsx", "xls"}:
            try:
                from openpyxl import load_workbook
                workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
                sheet = workbook.active
                rows = list(sheet.values)
                if not rows:
                    return []
                headers = [str(value or "").strip() for value in rows[0]]
                return [dict(zip(headers, row)) for row in rows[1:] if any(value is not None for value in row)]
            except Exception as exc:
                raise CMSModelImportError("CMS Excel file could not be read") from exc
        try:
            return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise CMSModelImportError("CMS file must be UTF-8 CSV or XLSX") from exc

    @staticmethod
    def _normalize_row(row: dict) -> dict:
        aliases = {
            "model family": "model_family", "model_family": "model_family", "model": "model_family",
            "version": "version", "model version": "version", "model_version": "version",
            "category": "category", "hcc category": "category", "hcc_category": "category",
            "hcc": "hcc_code", "hcc code": "hcc_code", "hcc_code": "hcc_code",
            "hcc name": "hcc_name", "hcc description": "hcc_name", "hcc_name": "hcc_name",
            "icd10": "icd10_code", "icd-10": "icd10_code", "icd-10-cm": "icd10_code",
            "icd10 code": "icd10_code", "icd-10-cm code": "icd10_code", "icd10_code": "icd10_code",
            "raf": "raf_score", "raf score": "raf_score", "coefficient": "raf_score", "raf_score": "raf_score",
        }
        normalized = {}
        for key, value in row.items():
            canonical = aliases.get(str(key).strip().lower())
            if canonical:
                normalized[canonical] = "" if value is None else str(value).strip()
        return normalized

    def _load(self) -> None:
        if not os.path.exists(self.registry_path):
            return
        try:
            with open(self.registry_path, "r", encoding="utf-8") as stream:
                for raw_model in json.load(stream):
                    model = CMSModel(
                        model_family=raw_model["model_family"], version=raw_model["version"],
                        source_name=raw_model["source_name"], source_sha256=raw_model["source_sha256"],
                        imported_at=datetime.fromisoformat(raw_model["imported_at"]),
                        mappings=[CMSMapping(**mapping) for mapping in raw_model["mappings"]],
                    )
                    self._models[(model.model_family, model.version)] = model
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise CMSModelImportError("CMS model registry could not be read") from exc

    def _save(self) -> None:
        directory = os.path.dirname(self.registry_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = []
        for model in self._models.values():
            payload.append({
                "model_family": model.model_family, "version": model.version,
                "source_name": model.source_name, "source_sha256": model.source_sha256,
                "imported_at": model.imported_at.isoformat(),
                "mappings": [mapping.__dict__ for mapping in model.mappings],
            })
        temporary_path = f"{self.registry_path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
        os.replace(temporary_path, self.registry_path)


try:
    from backend.app.core.config import CMS_MODELS_FILE
except ImportError:  # pragma: no cover - supports direct module use
    CMS_MODELS_FILE = "instance/cms_models.json"

cms_model_service = CMSModelService(CMS_MODELS_FILE)
