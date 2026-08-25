from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.app.core.config import ACCOUNT_LOCKOUT_MINUTES, AUTH_USERS_FILE, MAX_FAILED_LOGIN_ATTEMPTS
from backend.app.core.security import JWTManager, PasswordHasher
from backend.app.models.user import UserRecord
from backend.app.repositories.user_repository import InMemoryUserRepository, JsonUserRepository


class AuthError(Exception):
    """Raised when authentication or account state is invalid."""


class AuthService:
    """Centralized authentication service for secure user sign-in and session issuance."""

    def __init__(
        self,
        repository: Optional[InMemoryUserRepository] = None,
        password_hasher: Optional[PasswordHasher] = None,
        jwt_manager: Optional[JWTManager] = None,
        max_failed_attempts: int = MAX_FAILED_LOGIN_ATTEMPTS,
        lockout_minutes: int = ACCOUNT_LOCKOUT_MINUTES,
    ) -> None:
        self.repository = repository or JsonUserRepository(AUTH_USERS_FILE)
        self.password_hasher = password_hasher or PasswordHasher()
        self.jwt_manager = jwt_manager or JWTManager()
        self.max_failed_attempts = max_failed_attempts
        self.lockout_minutes = lockout_minutes

    def register_user(self, username: str, email: str, password: str, role: str = "coder") -> UserRecord:
        if self.repository.get_user_by_username(username):
            raise AuthError("Username already exists")

        user = UserRecord(
            username=username,
            email=email,
            role=role,
            password_hash=self.password_hasher.hash_password(password),
        )
        return self.repository.create_user(user)

    def authenticate_user(self, username: str, password: str, ip_address: str) -> Dict[str, Any]:
        user = self.repository.get_user_by_username(username)
        if not user:
            raise AuthError("Invalid credentials")

        if not user.is_active:
            self.repository.record_login_attempt(user.user_id, ip_address, False)
            raise AuthError("Account inactive")

        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            self.repository.record_login_attempt(user.user_id, ip_address, False)
            raise AuthError("Account locked")

        if not self.password_hasher.verify_password(password, user.password_hash):
            self.repository.record_login_attempt(user.user_id, ip_address, False)
            user.failed_login_count += 1
            if user.failed_login_count >= self.max_failed_attempts:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=self.lockout_minutes)
                self.repository.update_user(user)
                raise AuthError("Too many failed attempts; account locked")
            self.repository.update_user(user)
            raise AuthError("Invalid credentials")

        user.failed_login_count = 0
        user.last_login_at = datetime.now(timezone.utc)
        self.repository.update_user(user)
        self.repository.record_login_attempt(user.user_id, ip_address, True)

        return {
            "user": user,
            "access_token": self.jwt_manager.create_access_token(user),
        }

    def get_user_from_token(self, token: str) -> UserRecord:
        payload = self.jwt_manager.decode_access_token(token)
        user_id = int(payload["sub"])
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise AuthError("User not found")
        return user


default_auth_service = AuthService()
