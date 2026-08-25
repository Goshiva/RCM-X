from __future__ import annotations

import io
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

    chart = client.get(f"/api/charts/{chart_id}", headers=coder_headers)
    assert chart.status_code == 200
    assert chart.get_json()["latest_risk_input"]["captured_icd10_codes"] == ["E11.9"]

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
    assert submit.get_json()["chart_status"] == "completed"
