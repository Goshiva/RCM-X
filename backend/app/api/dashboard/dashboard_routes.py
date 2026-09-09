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
from backend.app.services.chart_assignment_service import ChartAssignmentError
from backend.app.api.auth.auth_routes import auth_service
from backend.app.services.learning_service import CodingLearningService
from backend.app.core.config import AUDIT_LOG_FILE

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")
chart_service = chart_assignment_service
learning_service = CodingLearningService(audit_service)


def _coded_data_rows() -> list[dict]:
    """Flatten final chart submissions into one queryable row per ICD-10 code."""
    users = auth_service.repository
    rows = []
    for chart in chart_service.repository.list_charts():
        latest = risk_service.get_latest_for_chart(chart.chart_id)
        if not latest:
            continue
        coder = users.get_user_by_id(chart.l1_user_id) if chart.l1_user_id else None
        auditor = users.get_user_by_id(chart.l2_user_id) if chart.l2_user_id else None
        mappings = latest.mapped_hcc_versions or []
        for code in latest.captured_icd10_codes or []:
            mapping = next(
                (item for item in mappings if str(item.get("icd10", "")).upper() == str(code).upper()),
                {},
            )
            hcc = mapping.get("hcc", {}) if isinstance(mapping, dict) else {}
            if not isinstance(hcc, dict):
                hcc = {}
            rows.append({
                "chart_id": chart.chart_id,
                "filename": chart.original_filename,
                "status": chart.status,
                "icd10_code": code,
                "code_category": chart.category or hcc.get("category") or mapping.get("category") or "Uncategorized",
                "hcc_code": hcc.get("hcc_code") or hcc.get("hcc") or mapping.get("hcc_code") or mapping.get("hcc", ""),
                "hcc_name": hcc.get("description") or hcc.get("name") or mapping.get("description") or mapping.get("hcc_name", ""),
                "raf_score": latest.calculated_raf_score,
                "l1_coder": coder.username if coder else None,
                "l2_auditor": auditor.username if auditor else None,
                "coded_at": latest.updated_at.isoformat() if latest.updated_at else None,
            })
    return rows


@bp.route("/coder", methods=["GET"])
@require_auth
@require_roles("coder", "coder_l1", "coder_l2")
def coder_dashboard() -> tuple:
    user = request.current_user
    is_l2 = user.role == "coder_l2"
    quality_records = []
    for chart in chart_service.repository.list_charts():
        if chart.status != "audited":
            continue
        if (not is_l2 and chart.l1_user_id != user.user_id) or (is_l2 and chart.l2_user_id != user.user_id):
            continue
        latest = risk_service.get_latest_for_chart(chart.chart_id)
        quality = (latest.user_inputs or {}).get("audit_quality", {}) if latest else {}
        if quality:
            quality_records.append({"chart_id": chart.chart_id, **quality})
    total_lines = sum(item.get("l1_total_lines", 0) for item in quality_records)
    total_errors = sum(item.get("total_errors", 0) for item in quality_records)
    total_disputes = sum(len(item.get("disputed_errors", [])) for item in quality_records)
    if is_l2:
        quality_summary = {
            "audited_charts": len(quality_records),
            "reviewed_lines": total_lines,
            "l1_errors_identified": total_errors,
            "changes_without_l1_error": sum(len(item.get("l2_changes", [])) for item in quality_records),
            "disputes_reversed": total_disputes,
            "production_percent": round(
                len([chart for chart in chart_service.repository.list_charts() if chart.l2_user_id == user.user_id and chart.status == "audited"])
                / max(len([chart for chart in chart_service.repository.list_charts() if chart.l2_user_id == user.user_id]), 1) * 100,
                2,
            ),
        }
    else:
        quality_summary = {
            "audited_charts": len(quality_records),
            "total_lines": total_lines,
            "total_errors": max(total_errors - total_disputes, 0),
            "disputes_reversed": total_disputes,
            "accuracy": round(1 - (max(total_errors - total_disputes, 0) / max(total_lines, 1)), 4) if quality_records else None,
            "production_percent": round(
                len([chart for chart in chart_service.repository.list_charts() if chart.l1_user_id == user.user_id and chart.status in {"pending_audit", "audited"}])
                / max(len([chart for chart in chart_service.repository.list_charts() if chart.l1_user_id == user.user_id]), 1) * 100,
                2,
            ),
        }
    return jsonify({
        "success": True,
        "user": {"user_id": user.user_id, "username": user.username, "role": user.role},
        "workflow_stage": "l2" if is_l2 else "l1",
        "claim_bucket": 2 if is_l2 else 1,
        "assigned_chart_ids": [
            chart.chart_id for chart in chart_service.repository.list_charts()
            if chart.assigned_to_user_id == user.user_id
        ],
        "quality": quality_summary,
        "quality_records": quality_records,
    }), 200


def _team_quality_rows() -> list[dict]:
    rows = []
    for user in auth_service.repository._users_by_id.values():
        if user.role not in {"coder", "coder_l1", "coder_l2"}:
            continue
        charts = [
            chart for chart in chart_service.repository.list_charts()
            if (chart.l1_user_id if user.role != "coder_l2" else chart.l2_user_id) == user.user_id
        ]
        submissions = [
            record for record in risk_service.repository.get_all() if record.user_id == user.user_id
        ]
        quality = []
        for record in submissions:
            item = (record.user_inputs or {}).get("audit_quality")
            if item:
                quality.append(item)
        lines = sum(item.get("l1_total_lines", 0) for item in quality)
        errors = sum(item.get("total_errors", 0) for item in quality)
        rows.append({
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role,
            "production_charts": len({chart.chart_id for chart in charts}),
            "wip_charts": sum(chart.status in {"locked", "in_progress", "audit_locked"} for chart in charts),
            "production_percent": round(
                len([chart for chart in charts if chart.status in {"pending_audit", "audited"}])
                / max(len(charts), 1) * 100,
                2,
            ),
            "audited_charts": len(quality),
            "total_lines": lines,
            "total_errors": errors,
            "quality_percent": round(max(0, 1 - errors / max(lines, 1)) * 100, 2) if quality else None,
        })
    return rows


@bp.route("/team-quality", methods=["GET"])
@require_auth
@require_roles("supervisor", "manager", "admin", "master_admin")
def team_quality() -> tuple:
    return jsonify({"success": True, "users": _team_quality_rows()}), 200


@bp.route("/team-quality/<int:user_id>.xlsx", methods=["GET"])
@require_auth
@require_roles("supervisor", "manager", "admin", "master_admin")
def user_quality_export(user_id: int):
    user = auth_service.repository.get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "user_not_found"}), 404
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Coder Report"
    sheet.append(["User ID", "Username", "Role", "Chart ID", "Chart Status", "Audit Quality", "Errors", "Lines"])
    row_count = 0
    for chart in chart_service.repository.list_charts():
        assigned = chart.l1_user_id == user_id or chart.l2_user_id == user_id
        if not assigned:
            continue
        latest = risk_service.get_latest_for_chart(chart.chart_id)
        quality = (latest.user_inputs or {}).get("audit_quality", {}) if latest else {}
        sheet.append([
            user.user_id, user.username, user.role, chart.chart_id, chart.status,
            round(quality.get("accuracy", 0) * 100, 2) if quality else "",
            quality.get("total_errors", "") if quality else "",
            quality.get("l1_total_lines", "") if quality else "",
        ])
        row_count += 1
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"{user.username}_quality_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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
@require_roles("manager", "supervisor", "admin", "master_admin")
def supervisor_dashboard() -> tuple:
    charts = chart_service.repository.list_charts()
    submissions = risk_service.repository.get_all()
    production_charts_by_user = {}
    quality_rejections_by_user = {}
    for submission in submissions:
        production_charts_by_user.setdefault(submission.user_id, set()).add(submission.chart_id)
        decisions = (submission.user_inputs or {}).get("diagnosis_decisions", {})
        quality_rejections_by_user[submission.user_id] = quality_rejections_by_user.get(submission.user_id, 0) + sum(
            1 for decision in decisions.values() if decision.get("decision") == "rejected"
        )
    return jsonify({
        "success": True,
        "message": "Supervisor workspace ready",
        "buckets": {
            "bucket_1": sum(chart.status in {"queued", "released", "locked", "in_progress"} for chart in charts),
            "bucket_2": sum(chart.status in {"pending_audit", "audit_locked"} for chart in charts),
            "bucket_3": sum(chart.status == "audited" for chart in charts),
        },
        "production_by_user": {
            user_id: len(chart_ids) for user_id, chart_ids in production_charts_by_user.items()
        },
        "quality_rejections_by_user": quality_rejections_by_user,
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


@bp.route("/manager", methods=["GET"])
@require_auth
@require_roles("manager", "admin", "master_admin")
def manager_dashboard() -> tuple:
    return supervisor_dashboard()


@bp.route("/audit-bucket", methods=["GET"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def audit_bucket() -> tuple:
    """Return the restricted bucket-3 audit projection, without source files or OCR text."""
    users = auth_service.repository
    records = []
    for chart in chart_service.repository.list_charts():
        if chart.status != "audited":
            continue
        latest = risk_service.get_latest_for_chart(chart.chart_id)
        coder = users.get_user_by_id(chart.l1_user_id) if chart.l1_user_id else None
        auditor = users.get_user_by_id(chart.l2_user_id) if chart.l2_user_id else None
        records.append({
            "chart_id": chart.chart_id,
            "patient_details": chart.patient_details,
            "encounter_details": chart.encounter_details,
            "codes": latest.captured_icd10_codes if latest else [],
            "category": chart.category,
            "l1_username": coder.username if coder else None,
            "l2_username": auditor.username if auditor else None,
            "audited_at": chart.updated_at.isoformat() if chart.updated_at else None,
        })
    return jsonify({"success": True, "bucket": 3, "records": records, "count": len(records)}), 200


@bp.route("/coded-data", methods=["GET"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def coded_data() -> tuple:
    rows = _coded_data_rows()
    return jsonify({
        "success": True,
        "records": rows,
        "count": len(rows),
        "distinct_codes": len({row["icd10_code"] for row in rows}),
        "categories": sorted({row["code_category"] for row in rows}),
    }), 200


@bp.route("/export.xlsx", methods=["GET"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def export_coding_workbook():
    workbook = Workbook()
    coded_rows = _coded_data_rows()
    charts_sheet = workbook.active
    charts_sheet.title = "Charts"
    charts_sheet.append([
        "Chart ID", "Filename", "Status", "Coder", "Coder ID",
        "Submission Status", "Submitted At", "ICD-10 Codes", "RAF Score", "Diagnosis Decisions",
    ])
    codes_sheet = workbook.create_sheet("Codes")
    codes_sheet.append(["Chart ID", "Filename", "Status", "Coder", "Auditor", "ICD-10 Code", "Code Category", "HCC Code", "HCC Name", "RAF Score"])
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
        for row in [item for item in coded_rows if item["chart_id"] == chart.chart_id]:
            codes_sheet.append([
                row["chart_id"], row["filename"], row["status"], row["l1_coder"],
                row["l2_auditor"], row["icd10_code"], row["code_category"],
                row["hcc_code"], row["hcc_name"], row["raf_score"] or "",
            ])
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
@require_roles("coder", "coder_l1", "coder_l2")
def submit_coding() -> tuple:
    payload = request.get_json(silent=True) or {}
    chart_id = int(payload.get("chart_id", 0))
    chart = chart_service.repository.get_chart(chart_id)
    if not chart:
        return jsonify({"success": False, "error": "chart_not_found"}), 404
    if chart.assigned_to_user_id != request.current_user.user_id:
        return jsonify({"success": False, "error": "chart_not_assigned_to_coder"}), 403
    submitted_codes = list(dict.fromkeys(
        str(code).strip().upper() for code in payload.get("captured_icd10_codes", []) if str(code).strip()
    ))
    audit_quality = {}
    if request.current_user.role == "coder_l2":
        l1_records = [
            entry for entry in risk_service.repository.get_by_chart(chart_id)
            if chart.l1_user_id and entry.user_id == chart.l1_user_id
        ]
        l1_codes = l1_records[-1].captured_icd10_codes if l1_records else []
        missed_codes = sorted(set(l1_codes) - set(submitted_codes))
        added_codes = sorted(set(submitted_codes) - set(l1_codes))
        audit_decisions = payload.get("user_inputs", {}).get("audit_decisions", [])
        classified_errors = {
            str(item.get("code", "")).strip().upper()
            for item in audit_decisions
            if item.get("classification") == "l1_error"
        } & set(l1_codes)
        classified_changes = {
            str(item.get("code", "")).strip().upper()
            for item in audit_decisions
            if item.get("classification") == "l2_change"
        }
        wrong_codes = sorted(classified_errors)
        missed_codes = sorted(set(missed_codes) - classified_changes)
        l2_changes = sorted(classified_changes | (set(submitted_codes) - set(l1_codes)))
        total_lines = max(len(l1_codes), 1)
        total_errors = len(set(missed_codes) | set(wrong_codes))
        audit_quality = {
            "l1_total_lines": len(l1_codes),
            "total_errors": total_errors,
            "missed_codes": missed_codes,
            "wrong_codes": wrong_codes,
            "added_codes": added_codes,
            "l2_changes": l2_changes,
            "disputed_errors": [],
            "accuracy": max(0.0, round(1 - (total_errors / total_lines), 4)),
        }
        user_inputs = dict(payload.get("user_inputs", {}))
        user_inputs["audit_quality"] = audit_quality
    else:
        user_inputs = payload.get("user_inputs", {})

    try:
        chart.patient_details = payload.get("patient_details", chart.patient_details)
        chart.encounter_details = payload.get("encounter_details", chart.encounter_details)
        chart.category = str(payload.get("category", chart.category)).strip()
        chart = chart_service.submit_chart(
            chart_id=chart_id,
            user_id=request.current_user.user_id,
            actor_role=request.current_user.role,
        )
    except ChartAssignmentError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    record = risk_service.save_submission(
        chart_id=chart_id,
        user_id=request.current_user.user_id,
        user_inputs=user_inputs,
        captured_icd10_codes=submitted_codes,
        mapped_hcc_versions=payload.get("mapped_hcc_versions", []),
        calculated_raf_score=payload.get("calculated_raf_score"),
    )
    if request.current_user.role == "coder_l2" and audit_quality:
        learning_service.record_audit_feedback(
            chart_id=chart_id,
            user_id=request.current_user.user_id,
            quality=audit_quality,
        )
    audit_service.record_event(
        action_type="coding_submitted",
        entity_type="risk_adjustment_input",
        details={
            "chart_id": chart_id,
            "input_id": record.input_id,
            "status": chart.status,
            "bucket": 2 if chart.status == "pending_audit" else 3,
            "audit_quality": audit_quality,
        },
        user_id=request.current_user.user_id,
        chart_id=chart_id,
        entity_id=str(record.input_id),
        actor_role=request.current_user.role,
    )
    return jsonify({
        "success": True,
        "input_id": record.input_id,
        "chart_status": chart.status,
        "audit_quality": audit_quality,
        "learning_signals": learning_service.learned_signals() if request.current_user.role == "coder_l2" else {},
    }), 200


@bp.route("/quality-dispute", methods=["POST"])
@require_auth
@require_roles("coder", "coder_l1")
def dispute_quality_error() -> tuple:
    payload = request.get_json(silent=True) or {}
    chart_id = int(payload.get("chart_id", 0))
    code = str(payload.get("code", "")).strip().upper()
    chart = chart_service.repository.get_chart(chart_id)
    if not chart or chart.l1_user_id != request.current_user.user_id:
        return jsonify({"success": False, "error": "quality_record_not_found"}), 404
    latest = risk_service.get_latest_for_chart(chart_id)
    quality = dict((latest.user_inputs or {}).get("audit_quality", {})) if latest else {}
    if not quality or code not in set(quality.get("wrong_codes", [])) | set(quality.get("missed_codes", [])):
        return jsonify({"success": False, "error": "quality_error_not_found"}), 404
    quality["wrong_codes"] = [item for item in quality["wrong_codes"] if item != code]
    quality["missed_codes"] = [item for item in quality["missed_codes"] if item != code]
    quality["disputed_errors"] = sorted(set(quality.get("disputed_errors", []) + [code]))
    quality["total_errors"] = len(set(quality.get("missed_codes", [])) | set(quality["wrong_codes"]))
    quality["accuracy"] = max(0.0, round(1 - (quality["total_errors"] / max(quality.get("l1_total_lines", 0), 1)), 4))
    updated_inputs = dict(latest.user_inputs or {})
    updated_inputs["audit_quality"] = quality
    risk_service.update_submission(input_id=latest.input_id, user_inputs=updated_inputs)
    audit_service.record_event(
        action_type="quality_error_disputed",
        entity_type="coding_feedback",
        details={"chart_id": chart_id, "code": code, "resolution": "reverted"},
        user_id=request.current_user.user_id,
        chart_id=chart_id,
        actor_role=request.current_user.role,
    )
    return jsonify({"success": True, "audit_quality": quality}), 200


@bp.route("/activity-log", methods=["GET"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def download_activity_log():
    """Download the append-only JSONL activity log for operational review."""
    log_path = os.path.abspath(AUDIT_LOG_FILE)
    if not os.path.isfile(log_path):
        return jsonify({"success": False, "error": "activity_log_not_found"}), 404
    audit_service.record_event(
        action_type="activity_log_exported",
        entity_type="activity_log",
        details={"format": "jsonl"},
        user_id=request.current_user.user_id,
        actor_role=request.current_user.role,
    )
    return send_file(
        log_path,
        mimetype="application/x-ndjson",
        as_attachment=True,
        download_name="coding_activity.jsonl",
    )


@bp.route("/activity-log.xlsx", methods=["GET"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def export_activity_log_workbook():
    """Export structured activity events as an Excel workbook."""
    events = audit_service.repository.get_all()
    requested_user_id = request.args.get("user_id", type=int)
    if requested_user_id is not None:
        events = [event for event in events if event.user_id == requested_user_id]
    workbook = Workbook()
    activity_sheet = workbook.active
    activity_sheet.title = "Activity Log"
    activity_sheet.append([
        "Audit ID", "Timestamp", "Action", "Entity Type", "Entity ID",
        "Chart ID", "User ID", "Actor Role", "Details",
    ])
    for event in events:
        activity_sheet.append([
            event.audit_id,
            event.created_at.isoformat() if event.created_at else "",
            event.action_type,
            event.entity_type,
            event.entity_id or "",
            event.chart_id or "",
            event.user_id or "",
            event.details.get("actor_role", "") if isinstance(event.details, dict) else "",
            json.dumps(event.details, ensure_ascii=True, default=str),
        ])

    summary_sheet = workbook.create_sheet("Action Summary")
    summary_sheet.append(["Action", "Count"])
    action_counts = {}
    for event in events:
        action_counts[event.action_type] = action_counts.get(event.action_type, 0) + 1
    for action, count in sorted(action_counts.items()):
        summary_sheet.append([action, count])

    for sheet in workbook.worksheets:
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"
        for column_cells in sheet.columns:
            width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 80)
            sheet.column_dimensions[column_cells[0].column_letter].width = width

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    audit_service.record_event(
        action_type="activity_log_exported",
        entity_type="activity_log",
        details={"format": "xlsx", "event_count": len(events)},
        user_id=request.current_user.user_id,
        actor_role=request.current_user.role,
    )
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"coding_activity_{requested_user_id}.xlsx" if requested_user_id else "coding_activity.xlsx",
    )


@bp.route("/learning-signals", methods=["GET"])
@require_auth
@require_roles("manager", "supervisor", "admin", "master_admin")
def coding_learning_signals() -> tuple:
    return jsonify({"success": True, "signals": learning_service.learned_signals()}), 200
