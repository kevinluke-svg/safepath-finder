from datetime import datetime, timezone
import uuid
from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="traveller", nullable=False)  # traveller, moderator, administrator
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)  # active, suspended, demo
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    reports = relationship("CommunityReport", back_populates="reporter", foreign_keys="CommunityReport.reporter_id", cascade="all, delete-orphan")
    saved_journeys = relationship("SavedJourney", back_populates="user", cascade="all, delete-orphan")
    journey_history = relationship("JourneyHistory", back_populates="user", cascade="all, delete-orphan")
    trusted_contacts = relationship("TrustedContact", back_populates="user", cascade="all, delete-orphan")
    journey_shares = relationship("JourneyShare", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_users_role_status", "role", "status"),
    )
