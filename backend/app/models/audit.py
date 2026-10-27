from datetime import datetime, timezone
import uuid
from typing import Optional
from sqlalchemy import String, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"aud-{uuid.uuid4().hex[:10]}")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    record: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(30), default="System", nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), default="Success", nullable=False)
    environment: Mapped[str] = mapped_column(String(50), default="Production API", nullable=False)

    __table_args__ = (
        Index("ix_audit_action_timestamp", "action", "timestamp"),
    )
