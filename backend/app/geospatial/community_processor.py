"""
SafePath Finder — Community Feedback & Reports Evidence Processor
Reconciles crowdsourced community observations with pedestrian street segments.
Enforces strict privacy detachment (no reporter PII), separates administrative moderation
from factual certainty, and manages duplicate, stale, and conflicting reports.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session

from app.models.report import CommunityReport
from app.models.feedback import Feedback
from app.geospatial.study_area import StudyArea
from app.geospatial.spatial_matcher import SpatialMatcher, SpatialMatchResult

logger = logging.getLogger(__name__)

# Documented Category Taxonomy Mapping from User Inputs to Evidence Observations
FEEDBACK_CATEGORY_MAPPING = {
    # Lighting concerns
    "lighting": ("lighting", "lighting_concern"),
    "broken_lighting": ("lighting", "broken_luminaire"),
    "dark_corridor": ("lighting", "dark_corridor"),
    "lighting_accuracy": ("lighting", "audit_discrepancy"),

    # Harassment & personal security
    "harassment": ("community_hazard", "harassment"),
    "threatening_behavior": ("community_hazard", "threatening_behavior"),
    "catcalling": ("community_hazard", "harassment"),
    "safety_concern": ("community_hazard", "personal_safety_concern"),

    # Direct incidents
    "crime": ("safety_incident", "reported_crime"),
    "theft": ("safety_incident", "reported_theft"),
    "safety_incident": ("safety_incident", "reported_incident"),

    # Physical access & obstruction
    "obstruction": ("community_hazard", "access_obstruction"),
    "broken_pavement": ("community_hazard", "pavement_hazard"),
    "construction_debris": ("community_hazard", "pathway_obstruction"),
    "waterlogging": ("community_hazard", "drainage_hazard"),

    # Street dog encounters & sightings (Priority 2 & 5)
    "dog_sighting": ("dog_encounter", "dog_sighting"),
    "dog_group": ("dog_encounter", "dog_group"),
    "dog_aggressive": ("dog_encounter", "dog_aggressive"),
    "dog_bite": ("dog_encounter", "dog_bite"),

    # General / Civic
    "routing_quality": ("civic_observation", "routing_quality_feedback"),
    "app_bug": ("civic_observation", "technical_feedback"),
    "general": ("civic_observation", "general_observation")
}


@dataclass
class ProcessedCommunityObservation:
    """Sanitized, PII-stripped community observation ready for network matching."""
    report_id: str
    source_type: str  # "community_report" or "user_feedback"
    evidence_category: str
    subcategory: str
    latitude: Optional[float]
    longitude: Optional[float]
    observed_at: datetime
    submitted_at: datetime
    moderation_status: str  # "approved", "pending", "flagged", "rejected"
    verification_status: str  # "admin_reviewed_community_report", "unverified_community_submission"
    confidence: str  # "moderate", "low"
    data_state: str  # "present", "stale", "conflicting"
    corroborations_count: int
    is_duplicate: bool
    is_fixture: bool
    description_summary: str
    limitations: List[str]
    dog_count: Optional[int] = None
    is_aggressive: Optional[bool] = None
    encounter_time: Optional[datetime] = None
    match_result: Optional[SpatialMatchResult] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["observedAt"] = self.observed_at.isoformat()
        d["submittedAt"] = self.submitted_at.isoformat()
        if self.encounter_time:
            d["encounterTime"] = self.encounter_time.isoformat()
        return d


class CommunityProcessor:
    """
    Processes community submissions into standardized evidence observations.
    Strips reporter personal identities, separates administrative moderation
    from ground-truth certainty, and manages duplicate and stale reports.
    """

    def __init__(
        self,
        stale_threshold_days: int = 180,
        duplicate_window_hours: int = 24,
        duplicate_distance_meters: float = 30.0,
        spatial_tolerance_meters: float = 30.0
    ):
        self.stale_threshold_days = stale_threshold_days
        self.duplicate_window_hours = duplicate_window_hours
        self.duplicate_distance_meters = duplicate_distance_meters
        self.spatial_tolerance_meters = spatial_tolerance_meters

    def process_community_reports(
        self,
        db: Session,
        study_area: StudyArea,
        matcher: Optional[SpatialMatcher] = None
    ) -> Tuple[List[ProcessedCommunityObservation], Dict[Tuple[int, int, int], List[ProcessedCommunityObservation]]]:
        """
        Extracts, deduplicates, and spatially matches community reports.
        Strictly excludes any reporter personal details.
        """
        reports = db.query(CommunityReport).all()
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(days=self.stale_threshold_days)

        processed_list: List[ProcessedCommunityObservation] = []
        edge_map: Dict[Tuple[int, int, int], List[ProcessedCommunityObservation]] = {}

        # Spatial-temporal cluster index for duplicate detection
        seen_clusters: List[Tuple[float, float, datetime, str, str]] = []

        for r in reports:
            # Map input category to documented evidence taxonomy
            cat_input = (r.category or "general").strip().lower()
            ev_cat, sub_cat = FEEDBACK_CATEGORY_MAPPING.get(cat_input, ("civic_observation", cat_input))

            # Distinguish occurrence date from submission date
            created_dt = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)
            if getattr(r, "encounter_time", None):
                enc_time = r.encounter_time if r.encounter_time.tzinfo else r.encounter_time.replace(tzinfo=timezone.utc)
                observed_dt = enc_time
            else:
                observed_dt = created_dt

            # Moderation vs Certainty: Administrator review verifies policy, not absolute ground truth
            if r.status == "approved":
                verification = "admin_reviewed_community_report"
                confidence = "moderate"
            elif r.status in {"flagged", "rejected"}:
                verification = "rejected_or_flagged_submission"
                confidence = "low"
            else:
                verification = "unverified_community_submission"
                confidence = "low"

            # Check Stale
            is_stale = (observed_dt < stale_cutoff)
            data_state = "stale" if is_stale else "present"

            # Check Duplicate / Cluster
            is_duplicate = False
            lat = r.latitude
            lon = r.longitude

            if lat is not None and lon is not None:
                for c_lat, c_lon, c_time, c_cat, _ in seen_clusters:
                    if c_cat == ev_cat or (ev_cat == "dog_encounter" and c_cat.startswith("dog_")):
                        time_diff = abs((observed_dt - c_time).total_seconds())
                        if time_diff <= (self.duplicate_window_hours * 3600):
                            # Rough coordinate distance check
                            d_deg = math.hypot(lat - c_lat, lon - c_lon)
                            if d_deg <= 0.0003:  # ~30 meters
                                is_duplicate = True
                                break
                if not is_duplicate:
                    seen_clusters.append((lat, lon, observed_dt, ev_cat, r.id))

            is_fix = bool(r.provenance and "Demonstration" in r.provenance)

            limitations = [
                "Community report reflects individual perception and localized environmental context.",
                "Administrative approval confirms report suitability for display, not absolute ground-truth certainty."
            ]
            if is_stale:
                limitations.append(f"Observation is older than {self.stale_threshold_days} days and marked stale.")
            if is_duplicate:
                limitations.append("Report flagged as duplicate or clustered with a recent nearby submission.")

            obs = ProcessedCommunityObservation(
                report_id=r.id,
                source_type="community_report",
                evidence_category=ev_cat,
                subcategory=sub_cat,
                latitude=lat,
                longitude=lon,
                observed_at=observed_dt,
                submitted_at=created_dt,
                moderation_status=r.status,
                verification_status=verification,
                confidence=confidence,
                data_state=data_state,
                corroborations_count=r.corroborations or 1,
                is_duplicate=is_duplicate,
                is_fixture=is_fix,
                description_summary=r.description[:120] if r.description else "",
                limitations=limitations,
                dog_count=getattr(r, "dog_count", None),
                is_aggressive=getattr(r, "is_aggressive", None),
                encounter_time=getattr(r, "encounter_time", None)
            )

            # Spatial Matching to Pedestrian Network
            if matcher and lat is not None and lon is not None and study_area.contains_point(lat, lon):
                match_res = matcher.match_point(lat, lon, tolerance_meters=self.spatial_tolerance_meters)
                obs.match_result = match_res
                # Only approved, non-rejected reports link to routing edge metrics
                if match_res.status == "matched" and match_res.edge_u is not None and r.status == "approved":
                    edge_key = (match_res.edge_u, match_res.edge_v, match_res.edge_key or 0)
                    if edge_key not in edge_map:
                        edge_map[edge_key] = []
                    edge_map[edge_key].append(obs)

            processed_list.append(obs)

        return processed_list, edge_map


import math
