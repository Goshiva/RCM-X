from __future__ import annotations

import os
import io
from uuid import uuid4
from pathlib import Path

import fitz
from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from backend.app.core.middleware import require_auth, require_roles
from backend.app.core.config import WIP_MAX_CHARTS
from backend.app.core.config import WIP_MAX_CHARTS
from backend.app.models.chart import ChartRecord
from src.nlp_identifier import MEDICAL_CONDITIONS_DB  # Legacy condition database
from src.hcc_engine import get_hcc_from_icd10
from src.icd_mapper import ICD10Mapper
from backend.app.services.chart_assignment_service import ChartAssignmentError
from backend.app.services.workflow_services import (
    audit_service,
    chart_assignment_service,
    icd_validator,
    nlp_worker,
    risk_service,
)

bp = Blueprint("charts", __name__, url_prefix="/api/charts")
icd_mapper = ICD10Mapper()


def _latest_nlp_result(chart_id: int) -> dict:
    records = risk_service.repository.get_by_chart(chart_id)
    for record in reversed(records):
        result = (record.user_inputs or {}).get("nlp_result")
        if result:
            return result
    return {}


def _resolve_chart_file(file_path: str) -> str | None:
    candidates = [
        Path(file_path),
        Path(__file__).resolve().parents[4] / file_path,
        Path(os.getenv("UPLOAD_FOLDER", "uploads")) / Path(file_path).name,
    ]
    return next((str(candidate) for candidate in candidates if candidate.is_file()), None)


@bp.route("/upload", methods=["POST"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def upload_chart():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "no_file_provided"}), 400

    original_filename = secure_filename(uploaded_file.filename)
    if not original_filename.lower().endswith(".pdf"):
        return jsonify({"success": False, "error": "only_pdf_files_supported"}), 400

    upload_folder = os.getenv("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    stored_filename = f"{uuid4().hex}.pdf"
    file_path = os.path.join(upload_folder, stored_filename)
    uploaded_file.save(file_path)

    chart = chart_assignment_service.repository.create_chart(
        ChartRecord(file_path=file_path, original_filename=original_filename)
    )
    nlp_worker.enqueue(chart.chart_id)
    nlp_worker.run()
    audit_service.record_event(
        action_type="chart_uploaded",
        entity_type="chart",
        details={"chart_id": chart.chart_id, "original_filename": original_filename},
        user_id=request.current_user.user_id,
        chart_id=chart.chart_id,
        entity_id=str(chart.chart_id),
    )
    return jsonify({
        "success": True,
        "chart": {
            "chart_id": chart.chart_id,
            "original_filename": chart.original_filename,
            "status": chart.status,
        },
    }), 201


@bp.route("/upload-bulk", methods=["POST"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def upload_charts_bulk():
    uploaded_files = [item for item in request.files.getlist("files") if item and item.filename]
    if not uploaded_files:
        return jsonify({"success": False, "error": "no_files_provided"}), 400

    upload_folder = os.getenv("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    created = []
    for uploaded_file in uploaded_files:
        original_filename = secure_filename(uploaded_file.filename)
        if not original_filename.lower().endswith(".pdf"):
            continue
        file_path = os.path.join(upload_folder, f"{uuid4().hex}.pdf")
        uploaded_file.save(file_path)
        chart = chart_assignment_service.repository.create_chart(
            ChartRecord(file_path=file_path, original_filename=original_filename)
        )
        nlp_worker.enqueue(chart.chart_id)
        audit_service.record_event(
            action_type="chart_uploaded",
            entity_type="chart",
            details={"chart_id": chart.chart_id, "original_filename": original_filename, "bucket": 1},
            user_id=request.current_user.user_id,
            chart_id=chart.chart_id,
            entity_id=str(chart.chart_id),
        )
        created.append({"chart_id": chart.chart_id, "original_filename": original_filename, "status": chart.status})

    if not created:
        return jsonify({"success": False, "error": "only_pdf_files_supported"}), 400
    nlp_worker.run()
    return jsonify({"success": True, "charts": created, "count": len(created), "bucket": 1}), 201


@bp.route("/upload-config", methods=["GET"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def upload_config():
    upload_folder = Path(os.getenv("UPLOAD_FOLDER", "uploads")).resolve()
    return jsonify({
        "success": True,
        "upload_folder": str(upload_folder),
        "processing": "background",
        "message": "PDFs are stored immediately and NLP processing runs in the background.",
    }), 200


@bp.route("/claim", methods=["POST"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2", "admin", "master_admin")
def claim_chart():
    payload = request.get_json(silent=True) or {}
    try:
        chart = chart_assignment_service.claim_next_available_chart(
            user_id=request.current_user.user_id,
            actor_role=request.current_user.role,
        )
        if not chart:
            return jsonify({"success": True, "chart": None, "message": "No available chart"}), 200
        audit_service.record_event(
            action_type="chart_claimed",
            entity_type="chart",
            details={"chart_id": chart.chart_id, "status": chart.status},
            user_id=request.current_user.user_id,
            chart_id=chart.chart_id,
            entity_id=str(chart.chart_id),
            actor_role=request.current_user.role,
        )
        return jsonify({"success": True, "chart": {
            "chart_id": chart.chart_id,
            "file_path": chart.file_path,
            "status": chart.status,
            "assigned_to_user_id": chart.assigned_to_user_id,
            "locked_until": chart.locked_until.isoformat() if chart.locked_until else None,
        }}), 200
    except ChartAssignmentError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409


@bp.route("/wip", methods=["GET"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2")
def work_in_progress():
    charts = chart_assignment_service.get_user_wip(
        request.current_user.user_id,
        request.current_user.role,
    )
    return jsonify({
        "success": True,
        "limit": WIP_MAX_CHARTS,
        "count": len(charts),
        "remaining": max(0, WIP_MAX_CHARTS - len(charts)),
        "charts": [{
            "chart_id": chart.chart_id,
            "original_filename": chart.original_filename,
            "status": chart.status,
            "locked_until": chart.locked_until.isoformat() if chart.locked_until else None,
        } for chart in charts],
    }), 200


@bp.route("/current", methods=["GET"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2")
def current_chart():
    chart = chart_assignment_service.claim_next_available_chart(
        user_id=request.current_user.user_id,
        actor_role=request.current_user.role,
        resume_existing=True,
    )
    if not chart:
        return jsonify({"success": True, "chart": None}), 200
    audit_service.record_event(
        action_type="chart_claimed",
        entity_type="chart",
        details={"chart_id": chart.chart_id, "status": chart.status, "source": "current_chart"},
        user_id=request.current_user.user_id,
        chart_id=chart.chart_id,
        entity_id=str(chart.chart_id),
        actor_role=request.current_user.role,
    )
    return jsonify({
        "success": True,
        "chart": {
            "chart_id": chart.chart_id,
            "file_path": chart.file_path,
            "status": chart.status,
            "assigned_to_user_id": chart.assigned_to_user_id,
            "locked_until": chart.locked_until.isoformat() if chart.locked_until else None,
        },
    }), 200


@bp.route("/<int:chart_id>/release", methods=["POST"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2", "admin", "master_admin")
def release_chart(chart_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        released = chart_assignment_service.release_chart(
            chart_id=chart_id,
            actor_user_id=request.current_user.user_id,
            actor_role=request.current_user.role,
        )
        audit_service.record_event(
            action_type="chart_released",
            entity_type="chart",
            details={"chart_id": chart_id},
            user_id=request.current_user.user_id,
            chart_id=chart_id,
            entity_id=str(chart_id),
            actor_role=request.current_user.role,
        )
        return jsonify({"success": released}), 200 if released else 404
    except ChartAssignmentError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@bp.route("/<int:chart_id>/file", methods=["GET"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2", "manager", "supervisor", "admin", "master_admin")
def chart_file(chart_id: int):
    chart = chart_assignment_service.repository.get_chart(chart_id)
    chart_path = _resolve_chart_file(chart.file_path) if chart else None
    if not chart or not chart_path:
        return jsonify({"success": False, "error": "file_not_found"}), 404
    audit_service.record_event(
        action_type="chart_previewed",
        entity_type="chart",
        details={"chart_id": chart_id, "term": request.args.get("term", "").strip()},
        user_id=request.current_user.user_id,
        chart_id=chart_id,
        entity_id=str(chart_id),
        actor_role=request.current_user.role,
    )

    latest = risk_service.get_latest_for_chart(chart_id)
    requested_term = request.args.get("term", "").strip()
    terms = set()
    page_number = None
    if latest:
        nlp_result = _latest_nlp_result(chart_id)
        for entity in nlp_result.get("entities", []):
            if entity.get("type") != "condition":
                continue
            condition = entity.get("name", "")
            terms.add(condition)
            terms.update(MEDICAL_CONDITIONS_DB.get(condition, []))
        terms.update(latest.captured_icd10_codes or [])

    if requested_term:
        terms = {requested_term}
        for condition, synonyms in MEDICAL_CONDITIONS_DB.items():
            if requested_term.lower() == condition.lower():
                terms.update(synonyms)

    if not terms:
        return send_file(chart_path, mimetype="application/pdf", as_attachment=False)

    try:
        document = fitz.open(chart_path)
        annotation_count = 0
        for page in document:
            for term in terms:
                if not term:
                    continue
                for rectangle in page.search_for(term):
                    if page_number is None:
                        page_number = page.number + 1
                    annotation = page.add_highlight_annot(rectangle)
                    annotation.set_colors(stroke=(1, 0.75, 0.1))
                    annotation.update()
                    annotation_count += 1
        if annotation_count:
            pdf_bytes = document.tobytes(garbage=4, deflate=True)
            document.close()
            response = send_file(
                io.BytesIO(pdf_bytes),
                mimetype="application/pdf",
                as_attachment=False,
                download_name=f"highlighted_{chart.original_filename}",
            )
            response.headers["X-Diagnosis-Highlights"] = str(annotation_count)
            response.headers["X-Diagnosis-Page"] = str(page_number or 1)
            return response
        document.close()
    except (OSError, RuntimeError, ValueError):
        pass
    return send_file(chart_path, mimetype="application/pdf", as_attachment=False)


@bp.route("/<int:chart_id>/reassign", methods=["POST"])
@require_auth
@require_roles("admin", "master_admin")
def reassign_chart(chart_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        reassigned = chart_assignment_service.reassign_chart(
            chart_id=chart_id,
            new_user_id=int(payload.get("new_user_id", 0)),
            actor_user_id=request.current_user.user_id,
            actor_role=request.current_user.role,
        )
        return jsonify({"success": reassigned}), 200 if reassigned else 404
    except ChartAssignmentError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@bp.route("/<int:chart_id>/enqueue", methods=["POST"])
@require_auth
@require_roles("admin", "master_admin")
def enqueue_chart(chart_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        # Submit the processing task to Celery (or run eagerly if no broker configured)
        from backend.app.tasks.nlp_tasks import process_chart_task

        async_result = process_chart_task.apply_async(args=(chart_id,))
        return jsonify({"success": True, "queued": True, "chart_id": chart_id, "task_id": str(async_result.id)}), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.route("/<int:chart_id>", methods=["GET"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2", "manager", "supervisor", "admin", "master_admin")
def get_chart(chart_id: int):
    chart = chart_assignment_service.repository.get_chart(chart_id)
    if not chart:
        return jsonify({"success": False, "error": "not_found"}), 404
    audit_service.record_event(
        action_type="chart_opened",
        entity_type="chart",
        details={"chart_id": chart_id},
        user_id=request.current_user.user_id,
        chart_id=chart_id,
        entity_id=str(chart_id),
        actor_role=request.current_user.role,
    )

    latest = risk_service.get_latest_for_chart(chart_id)
    l1_submission = next(
        (
            record for record in risk_service.repository.get_by_chart(chart_id)
            if chart.l1_user_id and record.user_id == chart.l1_user_id
        ),
        None,
    )
    nlp_result = _latest_nlp_result(chart_id)
    audit_quality = (latest.user_inputs or {}).get("audit_quality", {}) if latest else {}
    return jsonify({
        "success": True,
        "chart": {
            "chart_id": chart.chart_id,
            "file_path": chart.file_path,
            "original_filename": chart.original_filename,
            "status": chart.status,
            "assigned_to_user_id": chart.assigned_to_user_id,
            "locked_until": chart.locked_until.isoformat() if chart.locked_until else None,
        },
        "latest_risk_input": {
            "input_id": latest.input_id if latest else None,
            "captured_icd10_codes": latest.captured_icd10_codes if latest else [],
            "user_inputs": latest.user_inputs if latest else {},
            "nlp_result": nlp_result,
            "l1_captured_icd10_codes": l1_submission.captured_icd10_codes if l1_submission else [],
            "audit_quality": audit_quality,
            "encounters": (latest.user_inputs or {}).get("encounters", []) if latest else [],
        }
    }), 200


@bp.route("/<int:chart_id>/encounters", methods=["POST"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2")
def add_encounter(chart_id: int):
    payload = request.get_json(silent=True) or {}
    date_of_service = str(payload.get("date_of_service", "")).strip()
    if not date_of_service:
        return jsonify({"success": False, "error": "date_of_service_required"}), 400
    try:
        from datetime import date
        date.fromisoformat(date_of_service)
    except ValueError:
        return jsonify({"success": False, "error": "date_of_service_must_be_yyyy_mm_dd"}), 400

    latest = risk_service.get_latest_for_chart(chart_id)
    inputs = dict(latest.user_inputs if latest else {})
    encounters = list(inputs.get("encounters", []))
    encounter = {
        "encounter_id": f"{chart_id}-{date_of_service}-{len(encounters) + 1}",
        "date_of_service": date_of_service,
        "provider": str(payload.get("provider", "")).strip(),
        "place_of_service": str(payload.get("place_of_service", "")).strip(),
        "note": str(payload.get("note", "")).strip(),
        "codes": [],
    }
    encounters.append(encounter)
    inputs["encounters"] = encounters
    record = risk_service.save_submission(
        chart_id=chart_id,
        user_id=request.current_user.user_id,
        user_inputs=inputs,
        captured_icd10_codes=latest.captured_icd10_codes if latest else [],
        mapped_hcc_versions=latest.mapped_hcc_versions if latest else [],
        calculated_raf_score=latest.calculated_raf_score if latest else None,
    )
    audit_service.record_event(
        action_type="encounter_created",
        entity_type="encounter",
        details=encounter,
        user_id=request.current_user.user_id,
        chart_id=chart_id,
        entity_id=encounter["encounter_id"],
        actor_role=request.current_user.role,
    )
    return jsonify({"success": True, "encounter": encounter, "input_id": record.input_id}), 201


@bp.route("/<int:chart_id>/add-code", methods=["POST"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2")
def add_code(chart_id: int):
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()
    user_id = request.current_user.user_id
    if not code:
        return jsonify({"success": False, "error": "no_code_provided"}), 400
    if not icd_validator.validate(code):
        return jsonify({"success": False, "error": "invalid_icd10_code"}), 400
    encounter_id = str(payload.get("encounter_id", "")).strip()

    latest = risk_service.get_latest_for_chart(chart_id)
    encounters = list((latest.user_inputs if latest else {}).get("encounters", []))
    encounter = next((item for item in encounters if item.get("encounter_id") == encounter_id), None)
    if not encounter:
        return jsonify({"success": False, "error": "valid_encounter_required_before_adding_code"}), 400
    existing_codes = latest.captured_icd10_codes if latest else []
    if code in existing_codes:
        return jsonify({"success": False, "error": "code_already_present"}), 400

    updated_codes = existing_codes + [code]
    encounter["codes"] = list(dict.fromkeys([*encounter.get("codes", []), code]))
    updated_inputs = dict(latest.user_inputs if latest else {})
    updated_inputs.update({"action": "add_code", "added_code": code, "encounters": encounters})

    record = risk_service.save_submission(
        chart_id=chart_id,
        user_id=user_id,
        user_inputs=updated_inputs,
        captured_icd10_codes=updated_codes,
        mapped_hcc_versions=[],
        calculated_raf_score=None,
    )

    audit_service.record_event(
        action_type="code_added",
        entity_type="chart",
        details={"chart_id": chart_id, "added_code": code, "encounter_id": encounter_id},
        user_id=user_id,
        chart_id=chart_id,
        entity_id=str(record.input_id),
        actor_role=request.current_user.role,
    )

    return jsonify({"success": True, "input_id": record.input_id, "captured_icd10_codes": updated_codes}), 200


@bp.route("/<int:chart_id>/diagnosis-decision", methods=["POST"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2")
def diagnosis_decision(chart_id: int):
    payload = request.get_json(silent=True) or {}
    diagnosis = str(payload.get("diagnosis", "")).strip()
    decision = str(payload.get("decision", "")).strip().lower()
    secondary_comment = str(payload.get("secondary_comment", "")).strip().lower()
    icd10_code = str(payload.get("icd10_code", "")).strip().upper()
    page_number = payload.get("page_number")
    if page_number is not None:
        try:
            page_number = max(1, int(page_number))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "page_number_must_be_positive"}), 400
    allowed_comments = {
        "accepted": {"support", "without_support"},
        "rejected": {"unconfirmed_diagnosis", "conflicting_diagnosis"},
    }
    if not diagnosis or decision not in {"accepted", "rejected"}:
        return jsonify({"success": False, "error": "diagnosis_and_valid_decision_required"}), 400
    if secondary_comment not in allowed_comments[decision]:
        return jsonify({"success": False, "error": "invalid_secondary_comment_for_decision"}), 400

    latest = risk_service.get_latest_for_chart(chart_id)
    existing_inputs = latest.user_inputs if latest else {}
    decisions = dict(existing_inputs.get("diagnosis_decisions", {}))
    decisions[diagnosis] = {
        "decision": decision,
        "secondary_comment": secondary_comment,
        "icd10_code": icd10_code,
        "page_number": page_number,
        "meat_evidence": payload.get("meat_evidence", []),
        "icd10_suggestions": payload.get("icd10_suggestions", []),
    }
    updated_inputs = dict(existing_inputs)
    updated_inputs["diagnosis_decisions"] = decisions
    record = risk_service.save_submission(
        chart_id=chart_id,
        user_id=request.current_user.user_id,
        user_inputs=updated_inputs,
        captured_icd10_codes=latest.captured_icd10_codes if latest else [],
        mapped_hcc_versions=latest.mapped_hcc_versions if latest else [],
        calculated_raf_score=latest.calculated_raf_score if latest else None,
    )
    audit_service.record_event(
        action_type=f"diagnosis_{decision}",
        entity_type="chart",
        details={"chart_id": chart_id, "diagnosis": diagnosis},
        user_id=request.current_user.user_id,
        chart_id=chart_id,
        entity_id=str(record.input_id),
        actor_role=request.current_user.role,
    )
    return jsonify({"success": True, "diagnosis": diagnosis, "decision": decision, "secondary_comment": secondary_comment}), 200


@bp.route("/<int:chart_id>/icd-evidence", methods=["GET"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2", "manager", "supervisor", "admin", "master_admin")
def icd_evidence(chart_id: int):
    chart = chart_assignment_service.repository.get_chart(chart_id)
    chart_path = _resolve_chart_file(chart.file_path) if chart else None
    if not chart or not chart_path:
        return jsonify({"success": False, "error": "file_not_found"}), 404
    latest = risk_service.get_latest_for_chart(chart_id)
    codes = latest.captured_icd10_codes if latest else []
    mappings = latest.mapped_hcc_versions if latest else []
    evidence = []
    document = fitz.open(chart_path)
    try:
        for code in codes:
            pages = [page.number + 1 for page in document if page.search_for(code)]
            mapping = next((item for item in mappings if item.get("icd10") == code), {})
            hcc = mapping.get("hcc") or get_hcc_from_icd10(code) or {}
            evidence.append({
                "icd10_code": code,
                "description": mapping.get("description") or icd_mapper.get_icd10_description(code),
                "category": hcc.get("category", "Uncategorized") if isinstance(hcc, dict) else "Uncategorized",
                "hcc": hcc,
                "page_numbers": pages,
            })
    finally:
        document.close()
    return jsonify({"success": True, "evidence": evidence}), 200


@bp.route("/validate-code", methods=["POST"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2", "admin", "master_admin")
def validate_code():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()
    suggestions = icd_validator.suggest(code)
    return jsonify({
        "success": True,
        "valid": icd_validator.validate(code),
        "suggestions": suggestions,
    }), 200
