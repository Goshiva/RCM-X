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


@bp.route("/unlock", methods=["POST"])
def unlock() -> tuple:
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "").strip()
    new_password = payload.get("password", "").strip() or "Coder123!"
    if not username:
        return jsonify({"success": False, "error": "Username required"}), 400

    user = auth_service.repository.get_user_by_username(username)
    if not user:
        return jsonify({"success": False, "error": f"User '{username}' not found"}), 404

    user.failed_login_count = 0
    user.locked_until = None
    user.is_active = True
    user.password_hash = auth_service.password_hasher.hash_password(new_password)
    auth_service.repository.update_user(user)

    return jsonify({
        "success": True,
        "message": f"Account '{username}' unlocked. Password set to '{new_password}'.",
        "username": username,
    }), 200
