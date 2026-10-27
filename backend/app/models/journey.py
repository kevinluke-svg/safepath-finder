from datetime import datetime, timezone
import uuid
from typing import Dict, Any
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class SavedJourney(Base):
    __tablename__ = "saved_journeys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    start: Mapped[str] = mapped_column(String(255), nullable=False)
    end: Mapped[str] = mapped_column(String(255), nullable=False)
    route_id: Mapped[str] = mapped_column(String(64), nullable=False)
    route_name: Mapped[str] = mapped_column(String(120), nullable=False)
    distance_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    preferences: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="saved_journeys")


class JourneyHistory(Base):
    __tablename__ = "journey_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"hist-{uuid.uuid4().hex[:8]}")
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    route_chosen: Mapped[str] = mapped_column(String(120), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    shared_with_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user = relationship("User", back_populates="journey_history")


class SavedPlace(Base):
    __tablename__ = "saved_places"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"plc-{uuid.uuid4().hex[:8]}")
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), default="place", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User")
