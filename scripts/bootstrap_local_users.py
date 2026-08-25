"""Create local development accounts for the manager, supervisor, and coder workflow."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.auth_service import AuthError, default_auth_service


USERS = (
    ("admin", "admin@example.com", "Admin123!", "admin"),
    ("manager", "manager@example.com", "Manager123!", "manager"),
    ("supervisor", "supervisor@example.com", "Supervisor123!", "supervisor"),
    ("coder", "coder@example.com", "Coder123!", "coder_l1"),
    ("auditor", "auditor@example.com", "Auditor123!", "coder_l2"),
)


for username, email, password, role in USERS:
    try:
        default_auth_service.register_user(username, email, password, role)
        print(f"created {role}: {username}")
    except AuthError as exc:
        print(f"skipped {username}: {exc}")
