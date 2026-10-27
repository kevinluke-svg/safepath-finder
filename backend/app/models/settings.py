from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    freshness_threshold_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    outdated_threshold_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    auto_flag_keywords: Mapped[str] = mapped_column(Text, default="harassment, assault, dark, broken, hazard", nullable=False)
    require_moderator_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evidence_weight_lighting: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    evidence_weight_activity: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    time_weight: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
