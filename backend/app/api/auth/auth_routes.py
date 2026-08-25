from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.app.services.auth_service import AuthError, default_auth_service

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
auth_service = default_auth_service


@bp.route("/login", methods=["POST"])
def login() -> tuple:
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "")
    password = payload.get("password", "")
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")

    try:
        result = auth_service.authenticate_user(username=username, password=password, ip_address=ip_address)
        return jsonify({
            "success": True,
            "access_token": result["access_token"],
            "user": {
                "user_id": result["user"].user_id,
                "username": result["user"].username,
                "role": result["user"].role,
            },
        }), 200
    except AuthError as exc:
        return jsonify({"success": False, "error": str(exc)}), 401


@bp.route("/register", methods=["POST"])
def register() -> tuple:
    payload = request.get_json(silent=True) or {}
    try:
        user = auth_service.register_user(
            username=payload.get("username", ""),
            email=payload.get("email", ""),
            password=payload.get("password", ""),
            role="coder",
        )
        return jsonify({"success": True, "user_id": user.user_id, "role": user.role}), 201
    except AuthError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
