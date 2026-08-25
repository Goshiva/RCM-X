from __future__ import annotations

from sqlalchemy import (
    Integer,
    Boolean,
    Column,
    Integer as SQLInteger,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="coder")
    is_active = Column(Boolean, nullable=False, server_default="true")
    failed_login_count = Column(Integer, nullable=False, server_default="0")
    locked_until = Column(TIMESTAMP(timezone=True), nullable=True)
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Chart(Base):
    __tablename__ = "charts"
    chart_id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, default="queued")
    priority = Column(Integer, nullable=False, default=0)
    assigned_to_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    locked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    locked_until = Column(TIMESTAMP(timezone=True), nullable=True)
    uploaded_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    assignee = relationship("User", lazy="joined")


class RiskAdjustmentInput(Base):
    __tablename__ = "risk_adjustment_inputs"
    input_id = Column(Integer, primary_key=True, autoincrement=True)
    chart_id = Column(Integer, ForeignKey("charts.chart_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    user_inputs = Column(JSON, nullable=False)
    captured_icd10_codes = Column(JSON, nullable=False)
    mapped_hcc_versions = Column(JSON, nullable=False)
    calculated_raf_score = Column(Numeric(8, 4), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    chart_id = Column(Integer, ForeignKey("charts.chart_id"), nullable=True)
    action_type = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(255), nullable=True)
    details = Column(JSON, nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"
    task_id = Column(String(255), primary_key=True)
    chart_id = Column(Integer, ForeignKey("charts.chart_id"), nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
