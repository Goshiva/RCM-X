from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt

from backend.app.core.config import JWT_ACCESS_TOKEN_TTL_MINUTES, JWT_ALGORITHM, JWT_SECRET_KEY


class PasswordHasher:
    """bcrypt-based password hashing for strict credential protection."""

    def __init__(self, rounds: int = 12) -> None:
        self.rounds = rounds

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt(rounds=self.rounds)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class JWTManager:
    """Issue and validate short-lived access tokens for authenticated sessions."""

    def create_access_token(self, user: Any) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.user_id),
            "username": user.username,
            "role": user.role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=JWT_ACCESS_TOKEN_TTL_MINUTES)).timestamp()),
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> Dict[str, Any]:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
