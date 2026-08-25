from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UserRecord:
    username: str
    email: str
    role: str
    password_hash: str
    is_active: bool = True
    user_id: Optional[int] = None
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
