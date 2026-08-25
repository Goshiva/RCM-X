from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional

from backend.app.models.user import UserRecord


class InMemoryUserRepository:
    """Simple repository used for local development and tests before the Postgres-backed implementation is wired in."""

    def __init__(self) -> None:
        self._users: Dict[str, UserRecord] = {}
        self._users_by_id: Dict[int, UserRecord] = {}
        self._next_id = 1

    def create_user(self, user: UserRecord) -> UserRecord:
        if user.user_id is None:
            user.user_id = self._next_id
            self._next_id += 1
        user.created_at = user.created_at or datetime.now(timezone.utc)
        user.updated_at = user.updated_at or user.created_at
        self._users[user.username] = user
        self._users_by_id[user.user_id] = user
        return user

    def get_user_by_username(self, username: str) -> Optional[UserRecord]:
        return self._users.get(username)

    def get_user_by_id(self, user_id: int) -> Optional[UserRecord]:
        return self._users_by_id.get(user_id)

    def update_user(self, user: UserRecord) -> UserRecord:
        user.updated_at = datetime.now(timezone.utc)
        self._users[user.username] = user
        if user.user_id is not None:
            self._users_by_id[user.user_id] = user
        return user

    def record_login_attempt(self, user_id: int, ip_address: str, success: bool) -> None:
        _ = (user_id, ip_address, success)


class JsonUserRepository(InMemoryUserRepository):
    """Small persistent repository for local single-process deployments."""

    def __init__(self, file_path: str = "instance/users.json") -> None:
        self.file_path = file_path
        super().__init__()
        self._load()

    def create_user(self, user: UserRecord) -> UserRecord:
        user = super().create_user(user)
        self._save()
        return user

    def update_user(self, user: UserRecord) -> UserRecord:
        user = super().update_user(user)
        self._save()
        return user

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            return
        used_ids = set()
        normalized = False
        with open(self.file_path, "r", encoding="utf-8") as stream:
            for raw_user in json.load(stream):
                for field in ("created_at", "updated_at", "locked_until", "last_login_at"):
                    if raw_user.get(field):
                        raw_user[field] = datetime.fromisoformat(raw_user[field])
                try:
                    user_id = int(raw_user.get("user_id"))
                except (TypeError, ValueError):
                    user_id = None
                if user_id is None or user_id in used_ids:
                    normalized = True
                    user_id = self._next_id
                    while user_id in used_ids:
                        user_id += 1
                raw_user["user_id"] = user_id
                used_ids.add(user_id)
                self._next_id = max(self._next_id, user_id + 1)
                super().create_user(UserRecord(**raw_user))
            if normalized:
                self._save()

    def _save(self) -> None:
        directory = os.path.dirname(self.file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        users = []
        for user in self._users.values():
            raw_user = user.__dict__.copy()
            for field in ("created_at", "updated_at", "locked_until", "last_login_at"):
                if raw_user[field]:
                    raw_user[field] = raw_user[field].isoformat()
            users.append(raw_user)
        temporary_path = f"{self.file_path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as stream:
            json.dump(users, stream, indent=2)
        os.replace(temporary_path, self.file_path)
