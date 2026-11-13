from datetime import datetime, timezone
import uuid
from typing import Optional
from sqlalchemy import String, Text, Float, Boolean, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class CommunityReport(Base):
    __tablename__ = "community_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"rep-{uuid.uuid4().hex[:8]}")
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    category_label: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)  # pending, approved, rejected, flagged
    
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Encounter details (e.g. street dog encounters, hazards)
    encounter_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dog_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_aggressive: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    location_confidence: Mapped[str] = mapped_column(String(30), default="user_pinned", nullable=False)
    duplicate_of_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("community_reports.id", ondelete="SET NULL"), nullable=True)
    
    reporter_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reporter_name: Mapped[str] = mapped_column(String(120), default="Anonymous", nullable=False)
    provenance: Mapped[str] = mapped_column(String(255), nullable=False)
    corroborations: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    outdated_flags: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Moderation details
    moderator_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reports")
    reviewer = relationship("User", foreign_keys=[reviewed_by_id])
    corroboration_records = relationship("ReportCorroboration", back_populates="report", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_reports_status_created", "status", "created_at"),
        Index("ix_reports_category", "category"),
    )


class ReportCorroboration(Base):
    """
    Tracks community confirmation of reported street observations by distinct accounts.
    Guarantees that a single user cannot artificially inflate corroboration counts.
    """
    __tablename__ = "report_corroborations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"cor-{uuid.uuid4().hex[:8]}")
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), default="confirm_present", nullable=False)  # confirm_present, flag_outdated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    report = relationship("CommunityReport", back_populates="corroboration_records")
    user = relationship("User")

    __table_args__ = (
        Index("ix_corroboration_report_user", "report_id", "user_id", unique=True),
    )
