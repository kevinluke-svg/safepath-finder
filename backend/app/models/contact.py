from datetime import datetime, timezone
import uuid
from typing import Optional
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.models.base import Base


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"ct-{uuid.uuid4().hex[:8]}")
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted at rest via AES-128 Fernet
    relationship: Mapped[str] = mapped_column(String(100), default="Friend", nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted at rest via AES-128 Fernet
    notify_on_start: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_arrival: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = orm_relationship("User", back_populates="trusted_contacts")



class JourneyShare(Base):
    __tablename__ = "journey_shares"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"shr-{uuid.uuid4().hex[:8]}")
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    route_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    contact_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(50), default="pending_provider_integration", nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), default="None configured (Backend integration required)", nullable=False)
    preview_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = orm_relationship("User", back_populates="journey_shares")


class ArrivalConfirmation(Base):
    __tablename__ = "arrival_confirmations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"arr-{uuid.uuid4().hex[:8]}")
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    journey_id: Mapped[str] = mapped_column(String(64), nullable=False)
    arrival_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(50), default="pending_provider_integration", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = orm_relationship("User")
