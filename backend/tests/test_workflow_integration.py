from __future__ import annotations

import io
import time
import uuid

import fitz

from app import app
from backend.app.api.auth.auth_routes import default_auth_service
from backend.app.services.workflow_services import chart_repository


def _token(client, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()["access_token"]


def test_supervisor_upload_and_coder_claim_workflow() -> None:
    chart_repository._charts.clear()
    chart_repository._next_id = 1
    suffix = uuid.uuid4().hex
    supervisor = f"supervisor_{suffix}"
    coder = f"coder_{suffix}"
    password = "Secret123!"
    default_auth_service.register_user(supervisor, f"{supervisor}@example.com", password, "supervisor")
    default_auth_service.register_user(coder, f"{coder}@example.com", password, "coder")

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Office visit. Type 2 diabetes. ICD-10 E11.9.")
    pdf_bytes = document.tobytes()
    document.close()

    client = app.test_client()
    supervisor_headers = {"Authorization": f"Bearer {_token(client, supervisor, password)}"}
    upload = client.post(
        "/api/charts/upload",
        headers=supervisor_headers,
        data={"file": (io.BytesIO(pdf_bytes), "integration.pdf")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    chart_id = upload.get_json()["chart"]["chart_id"]

    coder_headers = {"Authorization": f"Bearer {_token(client, coder, password)}"}
    claim = client.post("/api/charts/claim", headers=coder_headers, json={})
    assert claim.status_code == 200
    assert claim.get_json()["chart"]["chart_id"] == chart_id

    chart = None
    for _ in range(100):
        chart = client.get(f"/api/charts/{chart_id}", headers=coder_headers)
        assert chart.status_code == 200
        latest_risk_input = chart.get_json()["latest_risk_input"]
        if latest_risk_input and latest_risk_input["captured_icd10_codes"] == ["E11.9"]:
            break
        time.sleep(0.05)
    assert chart.get_json()["latest_risk_input"]["captured_icd10_codes"] == ["E11.9"]
    wip = client.get("/api/charts/wip", headers=coder_headers)
    assert wip.status_code == 200
    assert wip.get_json()["count"] == 1
    encounter = client.post(
        f"/api/charts/{chart_id}/encounters",
        headers=coder_headers,
        json={"date_of_service": "2026-02-15", "provider": "Dr. Test"},
    )
    assert encounter.status_code == 201
    encounter_id = encounter.get_json()["encounter"]["encounter_id"]
    missing_encounter_code = client.post(
        f"/api/charts/{chart_id}/add-code",
        headers=coder_headers,
        json={"code": "I10"},
    )
    assert missing_encounter_code.status_code == 400
    added_code = client.post(
        f"/api/charts/{chart_id}/add-code",
        headers=coder_headers,
        json={"code": "I10", "encounter_id": encounter_id},
    )
    assert added_code.status_code == 200

    submit = client.post(
        "/api/dashboard/submit",
        headers=coder_headers,
        json={
            "chart_id": chart_id,
            "user_inputs": {"coder_note": "submitted without per-diagnosis decisions"},
            "captured_icd10_codes": ["E11.9"],
            "mapped_hcc_versions": [],
            "calculated_raf_score": None,
        },
    )
    assert submit.status_code == 200
    assert submit.get_json()["chart_status"] == "pending_audit"
    chart_after_submit = client.get(f"/api/charts/{chart_id}", headers=coder_headers)
    assert chart_after_submit.status_code == 200
    assert chart_after_submit.get_json()["latest_risk_input"]["nlp_result"]["entities"]
    preview = client.get(f"/api/charts/{chart_id}/file", headers=coder_headers)
    assert preview.status_code == 200
    assert preview.mimetype == "application/pdf"

    l2 = f"coder_l2_{suffix}"
    default_auth_service.register_user(l2, f"{l2}@example.com", password, "coder_l2")
    l2_headers = {"Authorization": f"Bearer {_token(client, l2, password)}"}
    audit_claim = client.post("/api/charts/claim", headers=l2_headers, json={})
    assert audit_claim.status_code == 200
    assert audit_claim.get_json()["chart"]["chart_id"] == chart_id

    audit_submit = client.post(
        "/api/dashboard/submit",
        headers=l2_headers,
        json={
            "chart_id": chart_id,
            "user_inputs": {
                "audit_note": "L2 reviewed",
                "audit_decisions": [{"code": "E11.9", "classification": "l2_change"}],
            },
            "captured_icd10_codes": ["E11.9"],
            "mapped_hcc_versions": [],
            "calculated_raf_score": None,
            "patient_details": {"patient_id": "PAT-001"},
            "encounter_details": {"encounter_id": "ENC-001"},
            "category": "diabetes",
        },
    )
    assert audit_submit.status_code == 200
    assert audit_submit.get_json()["chart_status"] == "audited"
    assert audit_submit.get_json()["audit_quality"]["total_errors"] == 0
    assert audit_submit.get_json()["audit_quality"]["l2_changes"] == ["E11.9"]
    assert audit_submit.get_json()["audit_quality"]["accuracy"] == 1.0
    learning = client.get("/api/dashboard/learning-signals", headers=supervisor_headers)
    assert learning.status_code == 200
    workbook = client.get("/api/dashboard/activity-log.xlsx", headers=supervisor_headers)
    assert workbook.status_code == 200
    assert workbook.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    coded_data = client.get("/api/dashboard/coded-data", headers=supervisor_headers)
    assert coded_data.status_code == 200
    assert coded_data.get_json()["records"][0]["icd10_code"] == "E11.9"
    assert coded_data.get_json()["records"][0]["code_category"] == "diabetes"

    audit_bucket = client.get("/api/dashboard/audit-bucket", headers=supervisor_headers)
    assert audit_bucket.status_code == 200
    audit_record = audit_bucket.get_json()["records"][0]
    assert set(audit_record) == {
        "chart_id", "patient_details", "encounter_details", "codes", "category",
        "l1_username", "l2_username", "audited_at",
    }
    assert audit_record["codes"] == ["E11.9"]
