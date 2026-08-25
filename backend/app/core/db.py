from __future__ import annotations

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

default_database_path = Path(__file__).resolve().parents[3] / "instance" / "risk_adjustment.db"
default_database_path.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{default_database_path.as_posix()}"

# Connection pool settings (tunable). File-backed SQLite survives restarts and
# avoids separate empty databases for different SQLAlchemy connections.
if DATABASE_URL.startswith("sqlite"):
    _engine = create_engine(DATABASE_URL, future=True)
else:
    _engine = create_engine(
        DATABASE_URL,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        future=True,
    )

SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)

# expose for quick use
engine = _engine
