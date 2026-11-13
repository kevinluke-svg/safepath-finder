"""
SafePath Finder — Community Reports & Environmental Observations Adapter
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session

from app.models.report import CommunityReport
from app.geospatial.study_area import StudyArea

logger = logging.getLogger(__name__)


@dataclass
class CommunityIncident:
    """Sanitized, PII-free community environmental report for route evaluation."""
    id: str
    category: str
    category_label: str
    location_text: str
    description: str
    status: str  # "approved", "pending", "flagged", "rejected"
    created_at: str
    corroborations: int
    is_fixture: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    encounter_time: Optional[datetime] = None
    dog_count: Optional[int] = None
    is_aggressive: Optional[bool] = None
    # Note: Strictly NO reporter_name, user_id, email, phone, or IP address

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CommunityAuditResult:
    """Summary of community evidence stored in the application database."""
    study_area_name: str
    total_reports_count: int
    approved_reports_count: int
    pending_reports_count: int
    flagged_reports_count: int
    rejected_reports_count: int
    categories_breakdown: Dict[str, int]
    usable_for_routing_count: int
    incidents: List[CommunityIncident]

    @property
    def records(self) -> List[CommunityIncident]:
        return self.incidents

    def to_dict(self) -> Dict[str, Any]:
        return {
            "studyAreaName": self.study_area_name,
            "totalReportsCount": self.total_reports_count,
            "approvedReportsCount": self.approved_reports_count,
            "pendingReportsCount": self.pending_reports_count,
            "flaggedReportsCount": self.flagged_reports_count,
            "rejectedReportsCount": self.rejected_reports_count,
            "categoriesBreakdown": self.categories_breakdown,
            "usableForRoutingCount": self.usable_for_routing_count,
            "incidents": [inc.to_dict() for inc in self.incidents]
        }


class BaseCommunityAdapter(ABC):
    """Abstract interface for community evidence extraction."""

    @abstractmethod
    def audit_community_reports(
        self,
        db: Session,
        study_area: StudyArea,
        only_approved: bool = True
    ) -> CommunityAuditResult:
        """Extracts community reports with strict PII detachment."""
        pass


class DatabaseCommunityAdapter(BaseCommunityAdapter):
    """
    Extracts community observations from the relational database.
    Enforces data minimization: excludes reporter names, IDs, and crowd density estimates.
    Distinguishes demonstration fixtures from live submissions.
    """

    def audit_community_reports(
        self,
        db: Session,
        study_area: StudyArea,
        only_approved: bool = True
    ) -> CommunityAuditResult:
        query = db.query(CommunityReport)
        all_reports = query.all()

        total = len(all_reports)
        approved = sum(1 for r in all_reports if r.status == "approved")
        pending = sum(1 for r in all_reports if r.status == "pending")
        flagged = sum(1 for r in all_reports if r.status == "flagged")
        rejected = sum(1 for r in all_reports if r.status == "rejected")

        categories_breakdown: Dict[str, int] = {}
        for r in all_reports:
            cat = r.category or "unspecified"
            categories_breakdown[cat] = categories_breakdown.get(cat, 0) + 1

        target_reports = [r for r in all_reports if (not only_approved or r.status == "approved")]

        incidents: List[CommunityIncident] = []
        for r in target_reports:
            # Distinguish test fixtures by inspecting provenance
            is_fixture = bool(r.provenance and "Demonstration" in r.provenance)

            # Strip all reporter identity fields (reporter_name, user_id)
            incidents.append(
                CommunityIncident(
                    id=r.id,
                    category=r.category,
                    category_label=r.category_label or r.category,
                    location_text=r.location,
                    description=r.description,
                    status=r.status,
                    created_at=r.created_at.isoformat() if r.created_at else datetime.now(timezone.utc).isoformat(),
                    corroborations=r.corroborations or 0,
                    is_fixture=is_fixture,
                    latitude=r.latitude,
                    longitude=r.longitude,
                    encounter_time=r.encounter_time,
                    dog_count=r.dog_count,
                    is_aggressive=r.is_aggressive
                )
            )

        return CommunityAuditResult(
            study_area_name=study_area.name,
            total_reports_count=total,
            approved_reports_count=approved,
            pending_reports_count=pending,
            flagged_reports_count=flagged,
            rejected_reports_count=rejected,
            categories_breakdown=categories_breakdown,
            usable_for_routing_count=len(incidents),
            incidents=incidents
        )
