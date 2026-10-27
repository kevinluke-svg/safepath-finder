"""
SafePath Finder — Segment Risk & Multi-Criteria Evidence Cost Model
Calculates normalized indicators (crime, lighting, community feedback, assistance access)
and derives effective edge risk R_effective and generalized travel cost Cost_e for Dijkstra routing.
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SegmentRiskProfile:
    """Detailed multi-criteria risk profile and generalized costs for an edge."""
    length_meters: float
    traversal_time_seconds: float

    # Normalized indicators [0.0 = minimal concern, 1.0 = maximal concern]
    crime_indicator: float
    crime_coverage: float

    lighting_indicator: float
    lighting_coverage: float

    community_indicator: float
    community_coverage: float

    assistance_indicator: float
    assistance_coverage: float

    # Facility walking times
    nearest_police_walking_minutes: Optional[float]
    nearest_hospital_walking_minutes: Optional[float]

    # Synthesized risk and uncertainty metrics
    observed_risk: float  # R_observed
    evidence_coverage: float  # Q in [0, 1]
    effective_risk: float  # R_effective = Q * R_obs + (1 - Q) * R_unknown
    has_insufficient_evidence: bool

    # Generalized Dijkstra edge costs
    cost_fastest: float  # lambda = 0
    cost_balanced: float  # lambda = lambda_balanced
    cost_safety: float  # lambda = lambda_safety

    # Contextual metadata
    lit_status: str
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SegmentRiskModel:
    """
    Evaluates pedestrian street network edges using transparent, multi-attribute utility theory.
    Avoids black-box scores and guarantees that missing data is never encoded as zero risk.
    """

    def __init__(
        self,
        walking_speed_mps: Optional[float] = None,
        lambda_balanced: Optional[float] = None,
        lambda_safety: Optional[float] = None,
        r_unknown_prior: Optional[float] = None,
        weight_crime: Optional[float] = None,
        weight_lighting: Optional[float] = None,
        weight_community: Optional[float] = None,
        weight_assistance: Optional[float] = None,
        min_coverage_threshold: Optional[float] = None
    ):
        self.walking_speed_mps = walking_speed_mps or settings.WALKING_SPEED_MPS
        self.lambda_balanced = lambda_balanced or settings.ROUTING_LAMBDA_BALANCED
        self.lambda_safety = lambda_safety or settings.ROUTING_LAMBDA_SAFETY
        self.r_unknown_prior = r_unknown_prior if r_unknown_prior is not None else settings.ROUTING_DEFAULT_R_UNKNOWN

        # Indicator weights
        self.w_crime = weight_crime if weight_crime is not None else settings.ROUTING_WEIGHT_CRIME
        self.w_lighting = weight_lighting if weight_lighting is not None else settings.ROUTING_WEIGHT_LIGHTING
        self.w_community = weight_community if weight_community is not None else settings.ROUTING_WEIGHT_COMMUNITY
        self.w_assistance = weight_assistance if weight_assistance is not None else settings.ROUTING_WEIGHT_ASSISTANCE
        self.min_coverage_threshold = min_coverage_threshold or settings.ROUTING_MIN_COVERAGE_THRESHOLD

        # Normalize weights to ensure sum = 1.0
        total_w = self.w_crime + self.w_lighting + self.w_community + self.w_assistance
        if total_w > 0:
            self.w_crime /= total_w
            self.w_lighting /= total_w
            self.w_community /= total_w
            self.w_assistance /= total_w

    def evaluate_edge(
        self,
        edge_data: Dict[str, Any],
        edge_length_meters: float,
        lit_status: str = "unmapped",
        police_walking_minutes: Optional[float] = None,
        hospital_walking_minutes: Optional[float] = None,
        crime_count: int = 0,
        crime_rate_per_km: float = 0.0,
        community_reports_count: int = 0,
        has_crime_dataset: bool = False
    ) -> SegmentRiskProfile:
        """
        Calculates multi-criteria risk profile and Dijkstra traversal costs for an edge.
        All edge costs are guaranteed to be finite and non-negative.
        """
        length_m = max(float(edge_length_meters), 1.0)
        traversal_time_s = max(round(length_m / self.walking_speed_mps, 2), 0.1)

        limitations: List[str] = []

        # 1. Crime Indicator (I_crime, Q_crime)
        if has_crime_dataset:
            # Normalized density: 10 incidents/km is scaled to 1.0 concern
            raw_density = crime_rate_per_km if crime_rate_per_km > 0 else (crime_count / (length_m / 1000.0))
            i_crime = min(round(raw_density / 10.0, 3), 1.0)
            q_crime = 1.0
        else:
            # When crime dataset is not configured/available, treat as unobserved
            i_crime = self.r_unknown_prior
            q_crime = 0.0
            limitations.append("Crime dataset unmapped; prior assumption applied.")

        # 2. Lighting Indicator (I_lighting, Q_lighting)
        raw_lit = (lit_status or "unmapped").lower().strip()
        if raw_lit in ("lit", "yes", "24/7", "automatic"):
            clean_lit = "lit"
            i_lighting = 0.10
            q_lighting = 1.0
        elif raw_lit in ("unlit", "no"):
            clean_lit = "unlit"
            i_lighting = 0.90
            q_lighting = 1.0
        elif raw_lit == "conflicting":
            clean_lit = "conflicting"
            i_lighting = 0.65
            q_lighting = 0.80
            limitations.append("Lighting has conflicting municipal vs community observations.")
        else:
            clean_lit = "unmapped"
            # Unmapped: Never assume dark! Preserved as prior
            i_lighting = self.r_unknown_prior
            q_lighting = 0.0
            limitations.append("Street lighting is unmapped on OpenStreetMap; uncertainty preserved.")

        # 3. Community Feedback Indicator (I_community, Q_community)
        has_community = bool(edge_data.get("has_community_dataset", False) or community_reports_count > 0)
        if has_community:
            if community_reports_count > 0:
                # Each verified hazard adds concern up to 1.0
                i_community = min(round(0.35 * community_reports_count, 3), 1.0)
                q_community = 1.0
            else:
                # Surveyed corridor with zero reports provides evidence of low community-reported hazard
                i_community = 0.05
                q_community = 0.70
        else:
            i_community = self.r_unknown_prior
            q_community = 0.0
            limitations.append("Community feedback data is unmapped; uncertainty preserved.")

        # 4. Assistance Access Indicator (I_assistance, Q_assistance)
        has_assistance = (police_walking_minutes is not None or hospital_walking_minutes is not None)
        if has_assistance:
            t_pol = police_walking_minutes if police_walking_minutes is not None else 999.0
            t_hosp = hospital_walking_minutes if hospital_walking_minutes is not None else 999.0
            min_access_time = min(t_pol, t_hosp)

            if min_access_time <= 5.0:  # Under 5 min walk (~360m)
                i_assistance = 0.10
                q_assistance = 1.0
            elif min_access_time <= 12.0:  # Under 12 min walk (~860m)
                i_assistance = 0.35
                q_assistance = 1.0
            elif min_access_time <= 20.0:  # Under 20 min walk (~1440m)
                i_assistance = 0.65
                q_assistance = 1.0
            elif min_access_time < 999.0:
                i_assistance = 0.85
                q_assistance = 0.80
            else:
                i_assistance = 0.95
                q_assistance = 0.80
                limitations.append("Civic assistance facilities are beyond 20 minutes walking access.")
        else:
            i_assistance = self.r_unknown_prior
            q_assistance = 0.0
            limitations.append("Civic assistance walking access is unmapped; uncertainty preserved.")

        # 5. Synthesize Evidence Coverage Q and Observed Risk R_observed
        # Total effective coverage: sum(w_i * q_i)
        coverage_q = (
            self.w_crime * q_crime +
            self.w_lighting * q_lighting +
            self.w_community * q_community +
            self.w_assistance * q_assistance
        )
        coverage_q = max(min(round(coverage_q, 4), 1.0), 0.0)

        # Observed Risk: weighted average over observed indicators
        weighted_observed_sum = (
            self.w_crime * q_crime * i_crime +
            self.w_lighting * q_lighting * i_lighting +
            self.w_community * q_community * i_community +
            self.w_assistance * q_assistance * i_assistance
        )
        if coverage_q > 0.001:
            r_observed = round(weighted_observed_sum / coverage_q, 4)
        else:
            r_observed = self.r_unknown_prior

        # Effective Risk: R_effective = Q * R_observed + (1 - Q) * R_unknown
        r_effective = round(coverage_q * r_observed + (1.0 - coverage_q) * self.r_unknown_prior, 4)

        has_insufficient = (coverage_q < self.min_coverage_threshold)
        if has_insufficient:
            limitations.append(f"Evidence coverage ({round(coverage_q*100, 1)}%) is below minimum threshold.")

        # 6. Generalized Edge Costs
        # Cost = T_e * (1 + lambda * R_effective)
        cost_fastest = traversal_time_s  # lambda = 0
        cost_balanced = round(traversal_time_s * (1.0 + self.lambda_balanced * r_effective), 2)
        cost_safety = round(traversal_time_s * (1.0 + self.lambda_safety * r_effective), 2)

        return SegmentRiskProfile(
            length_meters=length_m,
            traversal_time_seconds=traversal_time_s,
            crime_indicator=i_crime,
            crime_coverage=q_crime,
            lighting_indicator=i_lighting,
            lighting_coverage=q_lighting,
            community_indicator=i_community,
            community_coverage=q_community,
            assistance_indicator=i_assistance,
            assistance_coverage=q_assistance,
            nearest_police_walking_minutes=police_walking_minutes,
            nearest_hospital_walking_minutes=hospital_walking_minutes,
            observed_risk=r_observed,
            evidence_coverage=coverage_q,
            effective_risk=r_effective,
            has_insufficient_evidence=has_insufficient,
            cost_fastest=cost_fastest,
            cost_balanced=cost_balanced,
            cost_safety=cost_safety,
            lit_status=clean_lit,
            limitations=limitations
        )
