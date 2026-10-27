from datetime import datetime, timezone
import uuid
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.models.base import Base


class Feedback(Base):
    """
    User feedback submission record. Supports authenticated or anonymous submissions,
    metadata tracking, resolution status, and administrative review notes.
    """
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"fb-{uuid.uuid4().hex[:8]}")
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # routing_quality, lighting_accuracy, app_bug, safety_concern, general
    message: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1 to 5 stars
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False, index=True)  # new, under_review, resolved, archived
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = orm_relationship("User", foreign_keys=[user_id], backref="feedbacks")
    reviewer = orm_relationship("User", foreign_keys=[reviewed_by])
