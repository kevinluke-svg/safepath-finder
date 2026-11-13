from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, JSON, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    coverage: Mapped[str] = mapped_column(String(100), nullable=False)
    refresh_frequency: Mapped[str] = mapped_column(String(100), nullable=False)
    last_ingested: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    stale_warning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Open Data Provenance & Traceability Extensions
    source_organisation: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    licence: Mapped[str] = mapped_column(String(255), default="Open Database License (ODbL) 1.0", nullable=False)
    collection_period: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attribute_definitions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    limitations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    import_history = relationship("DatasetImportHistory", back_populates="source", cascade="all, delete-orphan")


class DatasetImportHistory(Base):
    """
    Tracks chronological dataset ingestion and verification audit logs.
    Ensures reproducibility, version tracking, and integrity of open datasets.
    """
    __tablename__ = "dataset_import_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("evidence_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    import_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    records_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)  # success, failed, unchanged
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    source = relationship("EvidenceSource", back_populates="import_history")


class StreetSegment(Base):
    __tablename__ = "street_segments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    route_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    street_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    coverage: Mapped[str] = mapped_column(String(30), nullable=False)  # adequate, limited, insufficient
    freshness: Mapped[str] = mapped_column(String(30), nullable=False)  # fresh, stale, outdated
    state: Mapped[str] = mapped_column(String(30), nullable=False)  # available, limited, insufficient
    risk_estimate: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    limitations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    attributes: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    timeline: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    geometry: Mapped[List[List[float]]] = mapped_column(JSON, default=list, nullable=False)

    # Geospatial network edge attributes
    edge_u: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    edge_v: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    edge_key: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    length_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lit_status: Mapped[str] = mapped_column(String(30), default="unmapped", nullable=False)  # lit, unlit, conflicting, unmapped
    nearest_police_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nearest_police_walking_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nearest_hospital_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nearest_hospital_walking_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    crime_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    crime_rate_per_km: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    community_reports_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Pedestrian Infrastructure attributes
    sidewalk_status: Mapped[str] = mapped_column(String(30), default="unmapped", nullable=False)  # both, left, right, separate, none, unmapped
    crossing_status: Mapped[str] = mapped_column(String(30), default="unmapped", nullable=False)  # traffic_signals, marked, unmarked, none, unmapped
    has_tactile_paving: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    crossing_difficulty: Mapped[str] = mapped_column(String(30), default="unknown", nullable=False)  # low, moderate, high, unknown
    infrastructure_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    evidence_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    observations = relationship("EvidenceObservation", back_populates="segment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_segments_route_freshness", "route_id", "freshness"),
    )


class EvidenceObservation(Base):
    """
    Standardized geospatial evidence observation unit.
    Represents an atomic, privacy-sanitized observation matched or associated with
    pedestrian network segments (crime, lighting, civic facilities, or community feedback).
    Excludes all personally identifiable reporter information.
    """
    __tablename__ = "evidence_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # crime_dataset, osm_lighting, osm_facility, community_report, user_feedback
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # crime, lighting, facility_access, community_hazard, safety_incident, civic_observation
    subcategory: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geometry: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    segment_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("street_segments.id", ondelete="SET NULL"), nullable=True, index=True)
    edge_u: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    edge_v: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    edge_key: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    match_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    match_method: Mapped[str] = mapped_column(String(50), default="unmatched", nullable=False)
    match_status: Mapped[str] = mapped_column(String(30), default="unmatched", nullable=False, index=True)  # matched, unmatched, ambiguous

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    source_attribution: Mapped[str] = mapped_column(String(255), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified", nullable=False)  # unverified, community_corroborated, admin_approved, official_record
    severity: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # low, medium, high, or None
    confidence: Mapped[str] = mapped_column(String(30), default="moderate", nullable=False)
    data_state: Mapped[str] = mapped_column(String(30), default="present", nullable=False, index=True)  # present, missing, stale, conflicting, insufficient
    provenance: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    limitations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    attributes: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    segment = relationship("StreetSegment", back_populates="observations")

    __table_args__ = (
        Index("ix_obs_cat_state", "category", "data_state"),
        Index("ix_obs_src_type_cat", "source_type", "category"),
    )

