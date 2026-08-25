from __future__ import annotations

import csv
import io

from openpyxl import Workbook

from backend.app.services.cms_model_service import CMSModelService


def test_imports_cms_hcc_v28_and_rxhcc_v08_with_aliases(tmp_path) -> None:
    service = CMSModelService(str(tmp_path / "cms_models.json"))
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["Model", "Model Version", "HCC Category", "HCC", "HCC Description", "ICD-10-CM Code", "Coefficient"])
    writer.writerow(["CMS-HCC", "V28", "Endocrine", "HCC018", "Diabetes", "E11.9", "0.124"])
    model = service.import_file(csv_buffer.getvalue().encode(), "cms_hcc_v28.csv")
    assert model.model_family == "CMS-HCC"
    assert service.lookup("E11.9", "CMS-HCC", "V28")[0]["hcc_code"] == "HCC018"

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["model_family", "version", "category", "hcc_code", "hcc_name", "icd10_code", "raf_score"])
    sheet.append(["RxHCC", "V08", "Endocrine", "RXHCC001", "Diabetes", "E11.9", 0.2])
    xlsx_buffer = io.BytesIO()
    workbook.save(xlsx_buffer)
    rx_model = service.import_file(xlsx_buffer.getvalue(), "rxhcc_v08.xlsx")
    assert rx_model.version == "V08"
    assert service.metadata("RxHCC", "V08")["imported"] is True

    reloaded = CMSModelService(str(tmp_path / "cms_models.json"))
    assert reloaded.lookup("E11.9", "CMS-HCC", "V28")
    assert reloaded.lookup("E11.9", "RxHCC", "V08")
