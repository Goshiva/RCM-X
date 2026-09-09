"""
Unlock a user account, reset failed login attempts, and set a new password.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.config import AUTH_USERS_FILE
from backend.app.core.security import PasswordHasher
from backend.app.repositories.user_repository import JsonUserRepository


def unlock_and_reset(username: str = "coder", new_password: str = "Coder123!"):
    repo = JsonUserRepository(AUTH_USERS_FILE)
    user = repo.get_user_by_username(username)
    if not user:
        print(f"[ERROR] User '{username}' not found in {AUTH_USERS_FILE}")
        return False

    ph = PasswordHasher()
    user.failed_login_count = 0
    user.locked_until = None
    user.is_active = True
    user.password_hash = ph.hash_password(new_password)
    repo.update_user(user)

    print("=" * 60)
    print(f"[SUCCESS] Account Unlocked & Password Reset")
    print(f"Username : {user.username}")
    print(f"Email    : {user.email}")
    print(f"Role     : {user.role}")
    print(f"Password : {new_password}")
    print(f"Status   : Active (Unlocked, 0 failed attempts)")
    print("=" * 60)
    return True


if __name__ == "__main__":
    target_user = sys.argv[1] if len(sys.argv) > 1 else "coder"
    target_pwd = sys.argv[2] if len(sys.argv) > 2 else "Coder123!"
    unlock_and_reset(target_user, target_pwd)
