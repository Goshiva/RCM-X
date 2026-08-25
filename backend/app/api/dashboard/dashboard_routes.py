from __future__ import annotations

import io
import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Font

from backend.app.core.middleware import require_auth, require_roles
from backend.app.services.workflow_services import (
    audit_service,
    chart_assignment_service,
    risk_service,
)
from backend.app.api.auth.auth_routes import auth_service

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")
chart_service = chart_assignment_service


@bp.route("/coder", methods=["GET"])
@require_auth
@require_roles("coder")
def coder_dashboard() -> tuple:
    user = request.current_user
    return jsonify({
        "success": True,
        "user": {"user_id": user.user_id, "username": user.username, "role": user.role},
        "message": "Coder workspace ready",
    }), 200


@bp.route("/admin", methods=["GET"])
@require_auth
@require_roles("admin", "master_admin")
def admin_dashboard() -> tuple:
    return jsonify({
        "success": True,
        "message": "Master admin workspace ready",
        "queue": [chart.chart_id for chart in chart_service.repository.list_charts()],
    }), 200


@bp.route("/supervisor", methods=["GET"])
@require_auth
@require_roles("supervisor", "admin", "master_admin")
def supervisor_dashboard() -> tuple:
    charts = chart_service.repository.list_charts()
    return jsonify({
        "success": True,
        "message": "Supervisor workspace ready",
        "queue": [
            {
                "chart_id": chart.chart_id,
                "original_filename": chart.original_filename,
                "status": chart.status,
                "assigned_to_user_id": chart.assigned_to_user_id,
                "priority": chart.priority,
            }
            for chart in charts
        ],
    }), 200


@bp.route("/export.xlsx", methods=["GET"])
@require_auth
@require_roles("supervisor", "admin", "master_admin")
def export_coding_workbook():
    workbook = Workbook()
    charts_sheet = workbook.active
    charts_sheet.title = "Charts"
    charts_sheet.append([
        "Chart ID", "Filename", "Status", "Coder", "Coder ID",
        "Submission Status", "Submitted At", "ICD-10 Codes", "RAF Score", "Diagnosis Decisions",
    ])
    codes_sheet = workbook.create_sheet("Codes")
    codes_sheet.append(["Chart ID", "Coder", "ICD-10 Code", "HCC Mappings"])
    decisions_sheet = workbook.create_sheet("Diagnosis Decisions")
    decisions_sheet.append(["Chart ID", "Coder", "Diagnosis", "Decision", "ICD Suggestions"])
    nlp_sheet = workbook.create_sheet("NLP Summary")
    nlp_sheet.append(["Chart ID", "Filename", "Document Type", "NLP Confidence", "Conditions", "OCR Text"])

    for sheet in workbook.worksheets:
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"

    for chart in chart_service.repository.list_charts():
        latest = risk_service.get_latest_for_chart(chart.chart_id)
        is_coder_submission = bool(latest and latest.user_id)
        coder = auth_service.repository.get_user_by_id(latest.user_id) if is_coder_submission else None
        coder_name = coder.username if coder else ""
        inputs = latest.user_inputs if latest else {}
        decisions = inputs.get("diagnosis_decisions", {})
        hcc_mappings = latest.mapped_hcc_versions if latest else []
        charts_sheet.append([
            chart.chart_id,
            chart.original_filename,
            chart.status,
            coder_name,
            latest.user_id if is_coder_submission else "",
            "Submitted" if is_coder_submission else "Not submitted",
            latest.created_at.isoformat() if latest and latest.created_at else "",
            ", ".join(latest.captured_icd10_codes or []) if latest else "",
            latest.calculated_raf_score if latest else "",
            json.dumps(decisions, ensure_ascii=True),
        ])
        for code in latest.captured_icd10_codes if latest else []:
            code_hccs = [item.get("hcc") for item in hcc_mappings if item.get("icd10") == code]
            codes_sheet.append([chart.chart_id, coder_name, code, json.dumps(code_hccs, ensure_ascii=True)])
        for diagnosis, decision in decisions.items():
            decisions_sheet.append([
                chart.chart_id,
                coder_name,
                diagnosis,
                decision.get("decision", ""),
                json.dumps(decision.get("icd10_suggestions", []), ensure_ascii=True),
            ])
        nlp_result = inputs.get("nlp_result", {})
        medical_entities = nlp_result.get("medical_entities", {})
        nlp_sheet.append([
            chart.chart_id,
            chart.original_filename,
            nlp_result.get("document_type", ""),
            nlp_result.get("confidence"),
            ", ".join(medical_entities.get("medical_conditions", [])),
            nlp_result.get("text", ""),
        ])

    for sheet in workbook.worksheets:
        for column_cells in sheet.columns:
            width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 60)
            sheet.column_dimensions[column_cells[0].column_letter].width = width

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    os.makedirs("reports", exist_ok=True)
    report_path = os.path.join(
        "reports", f"coding_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    with open(report_path, "wb") as report_file:
        report_file.write(output.getvalue())
    output.seek(0)
    audit_service.record_event(
        action_type="coding_exported",
        entity_type="coding_workbook",
        details={"format": "xlsx", "report_path": report_path},
        user_id=request.current_user.user_id,
    )
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="coding_results.xlsx",
    )


@bp.route("/submit", methods=["POST"])
@require_auth
@require_roles("coder")
def submit_coding() -> tuple:
    payload = request.get_json(silent=True) or {}
    chart_id = int(payload.get("chart_id", 0))
    chart = chart_service.repository.get_chart(chart_id)
    if not chart:
        return jsonify({"success": False, "error": "chart_not_found"}), 404
    if chart.assigned_to_user_id != request.current_user.user_id:
        return jsonify({"success": False, "error": "chart_not_assigned_to_coder"}), 403
    if chart.status == "completed":
        return jsonify({"success": False, "error": "chart_already_submitted"}), 409

    latest = risk_service.get_latest_for_chart(chart_id)
    record = risk_service.save_submission(
        chart_id=chart_id,
        user_id=request.current_user.user_id,
        user_inputs=payload.get("user_inputs", {}),
        captured_icd10_codes=payload.get("captured_icd10_codes", []),
        mapped_hcc_versions=payload.get("mapped_hcc_versions", []),
        calculated_raf_score=payload.get("calculated_raf_score"),
    )
    chart.status = "completed"
    chart.locked_until = None
    chart.locked_at = None
    chart_service.repository.update_chart(chart)
    audit_service.record_event(
        action_type="coding_submitted",
        entity_type="risk_adjustment_input",
        details={"chart_id": chart_id, "input_id": record.input_id, "status": "completed"},
        user_id=request.current_user.user_id,
        chart_id=chart_id,
        entity_id=str(record.input_id),
    )
    return jsonify({"success": True, "input_id": record.input_id, "chart_status": chart.status}), 200
