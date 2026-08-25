from __future__ import annotations

from functools import wraps
from typing import Callable, Any

from flask import jsonify, request

from backend.app.services.auth_service import AuthError, default_auth_service


auth_service = default_auth_service


def require_auth(fn: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif request.cookies.get("access_token"):
            token = request.cookies.get("access_token")

        if not token:
            return jsonify({"success": False, "error": "Authentication required"}), 401

        try:
            user = auth_service.get_user_from_token(token)
        except (AuthError, Exception):
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401

        request.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def require_roles(*roles: str):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not getattr(request, "current_user", None):
                return jsonify({"success": False, "error": "Authentication required"}), 401
            if request.current_user.role not in roles:
                return jsonify({"success": False, "error": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
