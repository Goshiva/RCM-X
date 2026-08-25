from __future__ import annotations

import os
import io
from uuid import uuid4

import fitz
from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from backend.app.core.middleware import require_auth, require_roles
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


@bp.route("/upload", methods=["POST"])
@require_auth
@require_roles("supervisor", "admin", "master_admin")
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
    # Local mode has no broker-backed worker; process the queued chart now.
    if not os.getenv("REDIS_BROKER_URL"):
        nlp_worker.process_next()
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


@bp.route("/claim", methods=["POST"])
@require_auth
@require_roles("coder", "admin", "master_admin")
def claim_chart():
    payload = request.get_json(silent=True) or {}
    try:
        chart = chart_assignment_service.claim_next_available_chart(
            user_id=request.current_user.user_id,
            actor_role=request.current_user.role,
        )
        if not chart:
            return jsonify({"success": True, "chart": None, "message": "No available chart"}), 200
        return jsonify({"success": True, "chart": {
            "chart_id": chart.chart_id,
            "file_path": chart.file_path,
            "status": chart.status,
            "assigned_to_user_id": chart.assigned_to_user_id,
            "locked_until": chart.locked_until.isoformat() if chart.locked_until else None,
        }}), 200
    except ChartAssignmentError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@bp.route("/current", methods=["GET"])
@require_auth
@require_roles("coder")
def current_chart():
    chart = chart_assignment_service.claim_next_available_chart(
        user_id=request.current_user.user_id,
        actor_role=request.current_user.role,
    )
    if not chart:
        return jsonify({"success": True, "chart": None}), 200
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
@require_roles("coder", "admin", "master_admin")
def release_chart(chart_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        released = chart_assignment_service.release_chart(
            chart_id=chart_id,
            actor_user_id=request.current_user.user_id,
            actor_role=request.current_user.role,
        )
        return jsonify({"success": released}), 200 if released else 404
    except ChartAssignmentError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@bp.route("/<int:chart_id>/file", methods=["GET"])
@require_auth
@require_roles("coder", "supervisor", "admin", "master_admin")
def chart_file(chart_id: int):
    chart = chart_assignment_service.repository.get_chart(chart_id)
    if not chart or not os.path.isfile(chart.file_path):
        return jsonify({"success": False, "error": "file_not_found"}), 404

    latest = risk_service.get_latest_for_chart(chart_id)
    requested_term = request.args.get("term", "").strip()
    terms = set()
    page_number = None
    if latest:
        nlp_result = (latest.user_inputs or {}).get("nlp_result", {})
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
        return send_file(chart.file_path, mimetype="application/pdf", as_attachment=False)

    try:
        document = fitz.open(chart.file_path)
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
    return send_file(chart.file_path, mimetype="application/pdf", as_attachment=False)


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
@require_roles("coder", "supervisor", "admin", "master_admin")
def get_chart(chart_id: int):
    chart = chart_assignment_service.repository.get_chart(chart_id)
    if not chart:
        return jsonify({"success": False, "error": "not_found"}), 404

    latest = risk_service.get_latest_for_chart(chart_id)
    nlp_result = (latest.user_inputs or {}).get("nlp_result", {}) if latest else {}
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
        }
    }), 200


@bp.route("/<int:chart_id>/add-code", methods=["POST"])
@require_auth
@require_roles("coder")
def add_code(chart_id: int):
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()
    user_id = request.current_user.user_id
    if not code:
        return jsonify({"success": False, "error": "no_code_provided"}), 400
    if not icd_validator.validate(code):
        return jsonify({"success": False, "error": "invalid_icd10_code"}), 400

    latest = risk_service.get_latest_for_chart(chart_id)
    existing_codes = latest.captured_icd10_codes if latest else []
    if code in existing_codes:
        return jsonify({"success": False, "error": "code_already_present"}), 400

    updated_codes = existing_codes + [code]

    record = risk_service.save_submission(
        chart_id=chart_id,
        user_id=user_id,
        user_inputs={"action": "add_code", "added_code": code},
        captured_icd10_codes=updated_codes,
        mapped_hcc_versions=[],
        calculated_raf_score=None,
    )

    audit_service.record_event(
        action_type="code_added",
        entity_type="chart",
        details={"chart_id": chart_id, "added_code": code},
        user_id=user_id,
        chart_id=chart_id,
        entity_id=str(record.input_id),
    )

    return jsonify({"success": True, "input_id": record.input_id, "captured_icd10_codes": updated_codes}), 200


@bp.route("/<int:chart_id>/diagnosis-decision", methods=["POST"])
@require_auth
@require_roles("coder")
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
    )
    return jsonify({"success": True, "diagnosis": diagnosis, "decision": decision, "secondary_comment": secondary_comment}), 200


@bp.route("/<int:chart_id>/icd-evidence", methods=["GET"])
@require_auth
@require_roles("coder", "supervisor", "admin", "master_admin")
def icd_evidence(chart_id: int):
    chart = chart_assignment_service.repository.get_chart(chart_id)
    if not chart or not os.path.isfile(chart.file_path):
        return jsonify({"success": False, "error": "file_not_found"}), 404
    latest = risk_service.get_latest_for_chart(chart_id)
    codes = latest.captured_icd10_codes if latest else []
    mappings = latest.mapped_hcc_versions if latest else []
    evidence = []
    document = fitz.open(chart.file_path)
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
@require_roles("coder", "admin", "master_admin")
def validate_code():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()
    suggestions = icd_validator.suggest(code)
    return jsonify({
        "success": True,
        "valid": icd_validator.validate(code),
        "suggestions": suggestions,
    }), 200
