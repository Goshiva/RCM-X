from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.app.core.middleware import require_auth, require_roles
from backend.app.services.cms_model_service import CMSModelImportError, cms_model_service

bp = Blueprint("cms", __name__, url_prefix="/api/cms")


@bp.route("/models", methods=["GET"])
@require_auth
def list_models():
    return jsonify({
        "success": True,
        "models": [
            {
                "model_family": model.model_family,
                "version": model.version,
                "source_name": model.source_name,
                "source_sha256": model.source_sha256,
                "imported_at": model.imported_at.isoformat(),
                "mapping_count": len(model.mappings),
            }
            for model in cms_model_service.list_models()
        ],
    }), 200


@bp.route("/models/import", methods=["POST"])
@require_auth
@require_roles("admin", "master_admin")
def import_model():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "no_file_provided"}), 400
    try:
        model = cms_model_service.import_file(
            uploaded_file.read(), uploaded_file.filename
        )
    except CMSModelImportError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({
        "success": True,
        "model_family": model.model_family,
        "version": model.version,
        "source_sha256": model.source_sha256,
        "mapping_count": len(model.mappings),
    }), 201


@bp.route("/models/<model_family>/<version>/categories", methods=["GET"])
@require_auth
def list_categories(model_family: str, version: str):
    return jsonify({
        "success": True,
        "model_family": model_family,
        "version": version,
        "categories": cms_model_service.categories(model_family, version),
    }), 200


@bp.route("/models/<model_family>/<version>", methods=["GET"])
@require_auth
def model_metadata(model_family: str, version: str):
    metadata = cms_model_service.metadata(model_family, version)
    if not metadata:
        return jsonify({"success": False, "error": "unsupported_model"}), 404
    return jsonify({"success": True, "model": metadata}), 200
