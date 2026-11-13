"""
SafePath Finder — Segment Risk & Multi-Criteria Evidence Cost Model (Phase 2)
Implements:
1. Multi-dimensional adverse risk model:
   R_observed(e) = w_c C(e) + w_l L(e) + w_d D(e) + w_f F(e) + w_p P(e) + w_a A(e)
   Where:
   - C(e): Crime-related risk density indicator
   - L(e): Street-lighting condition deficiency indicator
   - D(e): Street-dog encounter hazard indicator (differentiating calm sightings from aggressive encounters)
   - F(e): Community safety feedback / negative observation indicator
   - P(e): Pedestrian infrastructure deficiency indicator (sidewalks, crossings, tactile paving, obstructions)
   - A(e): Emergency facility isolation penalty indicator (separately visible as resilience/access)
2. Epistemological uncertainty policy:
   Q(e) = sum(w_i * q_i(e)) / sum(w_i)
   R_effective(e) = Q(e) * R_observed(e) + (1 - Q(e)) * R_unknown
   Missing evidence is strictly preserved as an uncertain prior, NEVER treated as zero risk.
3. Time-aware departure periods:
   - Daytime (06:00 - 18:00): Natural ambient light reduces artificial lighting relevance.
   - Evening (18:00 - 22:00): Twilight transition; lighting becomes active.
   - Night (22:00 - 06:00): Artificial illumination is paramount; heightened vigilance for aggressive packs and unlit corridors.
   *Fastest route calculation Cost_fastest = T(e) is strictly independent of departure period.*
4. Pedestrian restriction and step-free constraints:
   - Confirmed pedestrian-prohibited streets (foot=no, motorway) are assigned infinite cost.
   - Step-free preference avoids flights of stairs and severe crossing barriers.
"""

import math
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict, field

from app.core.config import settings
from app.geospatial.pedestrian_infrastructure import PedestrianInfrastructureProcessor

logger = logging.getLogger(__name__)

# Documented Temporal Weighting Profiles (Version 2.0.0)
TEMPORAL_PROFILES_V2: Dict[str, Dict[str, Any]] = {
    "daytime": {
        "description": "06:00 - 18:00 (Natural ambient sunlight). Artificial lighting has low impact; sidewalk presence and crossing accessibility dominate.",
        "weight_multipliers": {
            "lighting": 0.40,
            "infrastructure": 1.30,
            "dog": 1.00,
            "community": 1.00,
            "crime": 0.90,
            "assistance": 0.90
        }
    },
    "evening": {
        "description": "18:00 - 22:00 (Twilight / dusk transition). Artificial lighting becomes active and relevant; commercial and transit activity remain high.",
        "weight_multipliers": {
            "lighting": 1.00,
            "infrastructure": 1.00,
            "dog": 1.10,
            "community": 1.00,
            "crime": 1.00,
            "assistance": 1.00
        }
    },
    "night": {
        "description": "22:00 - 06:00 (Deep night / low footfall). Illumination is paramount; darkness, aggressive dog packs, and unverified corridors carry heightened concern.",
        "weight_multipliers": {
            "lighting": 1.60,
            "infrastructure": 0.80,
            "dog": 1.30,
            "community": 1.10,
            "crime": 1.20,
            "assistance": 1.10
        }
    }
}


@dataclass
class SegmentRiskProfile:
    """Detailed multi-criteria risk profile and generalized costs for an edge."""
    length_meters: float
    traversal_time_seconds: float

    # Normalized adverse indicators [0.0 = minimal concern, 1.0 = maximal concern]
    crime_indicator: float
    crime_coverage: float

    lighting_indicator: float
    lighting_coverage: float

    community_indicator: float
    community_coverage: float

    assistance_indicator: float
    assistance_coverage: float

    # Dog encounter indicator (Phase 1 & 2)
    dog_indicator: float = 0.5
    dog_coverage: float = 0.0
    dog_reports_count: int = 0

    # Pedestrian Infrastructure Deficiency indicator P(e) (Phase 2)
    infrastructure_indicator: float = 0.5
    infrastructure_coverage: float = 0.0
    sidewalk_status: str = "unmapped"
    crossing_status: str = "unmapped"
    crossing_difficulty: str = "unknown"
    has_tactile_paving: Optional[bool] = None
    has_active_obstruction: bool = False

    # Facility walking times
    nearest_police_walking_minutes: Optional[float] = None
    nearest_hospital_walking_minutes: Optional[float] = None

    # Synthesized risk and uncertainty metrics
    observed_risk: float = 0.5  # R_observed
    evidence_coverage: float = 0.0  # Q in [0, 1]
    effective_risk: float = 0.5  # R_effective = Q * R_obs + (1 - Q) * R_unknown
    has_insufficient_evidence: bool = True

    # Generalized Dijkstra edge costs
    cost_fastest: float = 1.0  # lambda = 0
    cost_balanced: float = 1.0  # lambda = lambda_balanced
    cost_safety: float = 1.0  # lambda = lambda_safety

    # Contextual metadata
    lit_status: str = "unmapped"
    departure_period: str = "daytime"
    is_pedestrian_prohibited: bool = False
    is_step_restricted: bool = False
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SegmentRiskModel:
    """
    Evaluates pedestrian street network edges using transparent, multi-attribute utility theory.
    Phase 2 version 2.0.0 integrates:
    - 6 distinct safety and infrastructure dimensions
    - Time-aware departure periods (daytime, evening, night)
    - Confirmed pedestrian restriction checks
    - Step-free accessibility routing constraints
    - Dynamic re-normalization of configurable weights
    """

    def __init__(
        self,
        model_version: str = "2.0.0",
        departure_period: Optional[str] = None,
        walking_speed_mps: Optional[float] = None,
        lambda_balanced: Optional[float] = None,
        lambda_safety: Optional[float] = None,
        r_unknown_prior: Optional[float] = None,
        weight_crime: Optional[float] = None,
        weight_lighting: Optional[float] = None,
        weight_community: Optional[float] = None,
        weight_infrastructure: Optional[float] = None,
        weight_dog: Optional[float] = None,
        weight_assistance: Optional[float] = None,
        min_coverage_threshold: Optional[float] = None,
        step_free: bool = False
    ):
        self.model_version = model_version or getattr(settings, "ROUTING_MODEL_VERSION", "2.0.0")
        self.departure_period = (departure_period or getattr(settings, "ROUTING_DEFAULT_DEPARTURE_PERIOD", "evening")).lower().strip()
        if self.departure_period not in TEMPORAL_PROFILES_V2:
            self.departure_period = getattr(settings, "ROUTING_DEFAULT_DEPARTURE_PERIOD", "evening").lower().strip()

        self.walking_speed_mps = walking_speed_mps or settings.WALKING_SPEED_MPS
        self.lambda_balanced = lambda_balanced or settings.ROUTING_LAMBDA_BALANCED
        self.lambda_safety = lambda_safety or settings.ROUTING_LAMBDA_SAFETY
        self.r_unknown_prior = r_unknown_prior if r_unknown_prior is not None else settings.ROUTING_DEFAULT_R_UNKNOWN
        self.min_coverage_threshold = min_coverage_threshold or settings.ROUTING_MIN_COVERAGE_THRESHOLD
        self.step_free = step_free

        # Base Configurable Indicator Weights (v2.0 baseline)
        self.base_w_crime = weight_crime if weight_crime is not None else getattr(settings, "ROUTING_WEIGHT_CRIME", 0.25)
        self.base_w_lighting = weight_lighting if weight_lighting is not None else getattr(settings, "ROUTING_WEIGHT_LIGHTING", 0.25)
        self.base_w_community = weight_community if weight_community is not None else getattr(settings, "ROUTING_WEIGHT_COMMUNITY", 0.15)
        self.base_w_infrastructure = weight_infrastructure if weight_infrastructure is not None else getattr(settings, "ROUTING_WEIGHT_INFRASTRUCTURE", 0.15)
        self.base_w_dog = weight_dog if weight_dog is not None else getattr(settings, "ROUTING_WEIGHT_DOG", 0.15)
        self.base_w_assistance = weight_assistance if weight_assistance is not None else getattr(settings, "ROUTING_WEIGHT_ASSISTANCE", 0.05)

        # Compute effective normalized weights for active departure period
        self._compute_effective_weights()

    def _compute_effective_weights(self) -> None:
        """Applies temporal multipliers to base weights and normalizes so sum = 1.0."""
        temporal_profile = TEMPORAL_PROFILES_V2.get(self.departure_period, TEMPORAL_PROFILES_V2["daytime"])
        multipliers = temporal_profile["weight_multipliers"]

        raw_w_crime = self.base_w_crime * multipliers.get("crime", 1.0)
        raw_w_lighting = self.base_w_lighting * multipliers.get("lighting", 1.0)
        raw_w_community = self.base_w_community * multipliers.get("community", 1.0)
        raw_w_infrastructure = self.base_w_infrastructure * multipliers.get("infrastructure", 1.0)
        raw_w_dog = self.base_w_dog * multipliers.get("dog", 1.0)
        raw_w_assistance = self.base_w_assistance * multipliers.get("assistance", 1.0)

        total_w = (
            raw_w_crime + raw_w_lighting + raw_w_community +
            raw_w_infrastructure + raw_w_dog + raw_w_assistance
        )

        if total_w > 0:
            self.w_crime = raw_w_crime / total_w
            self.w_lighting = raw_w_lighting / total_w
            self.w_community = raw_w_community / total_w
            self.w_infrastructure = raw_w_infrastructure / total_w
            self.w_dog = raw_w_dog / total_w
            self.w_assistance = raw_w_assistance / total_w
        else:
            self.w_crime = 0.25
            self.w_lighting = 0.25
            self.w_community = 0.15
            self.w_infrastructure = 0.15
            self.w_dog = 0.15
            self.w_assistance = 0.05

    def get_effective_weights(self) -> Dict[str, float]:
        """Returns the active normalized indicator weights."""
        return {
            "crime": round(self.w_crime, 4),
            "lighting": round(self.w_lighting, 4),
            "community": round(self.w_community, 4),
            "infrastructure": round(self.w_infrastructure, 4),
            "dog": round(self.w_dog, 4),
            "assistance": round(self.w_assistance, 4)
        }

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
        has_crime_dataset: bool = False,
        dog_reports: Optional[List[Any]] = None,
        dog_incidents_count: int = 0,
        sidewalk_status: Optional[str] = None,
        crossing_status: Optional[str] = None,
        crossing_difficulty: Optional[str] = None,
        has_tactile_paving: Optional[bool] = None,
        has_active_obstruction: Optional[bool] = None,
        wheelchair_accessible: Optional[str] = None,
        departure_period: Optional[str] = None,
        step_free: Optional[bool] = None
    ) -> SegmentRiskProfile:
        """
        Evaluates the 6 multi-dimensional indicators for a single network edge.
        Returns SegmentRiskProfile with non-negative, finite costs.
        Enforces pedestrian restriction and step-free constraints.
        """
        length_m = max(float(edge_length_meters), 1.0)
        traversal_time_s = max(round(length_m / self.walking_speed_mps, 2), 0.1)

        limitations: List[str] = []
        is_step_free_req = self.step_free if step_free is None else step_free
        dep_period = departure_period or self.departure_period

        # 0. Check Confirmed Pedestrian Restrictions
        foot_tag = str(edge_data.get("foot", "")).lower().strip()
        access_tag = str(edge_data.get("access", "")).lower().strip()
        highway_tag = edge_data.get("highway")
        if isinstance(highway_tag, list):
            highway_tag = highway_tag[0] if highway_tag else ""
        highway_tag = str(highway_tag).lower().strip()

        is_prohibited = (
            foot_tag in ("no", "private") or
            access_tag in ("private", "no") or
            highway_tag in ("motorway", "motorway_link")
        )

        is_step_restricted = False
        if is_step_free_req:
            is_stairs = (highway_tag in ("steps", "elevator") or edge_data.get("stairs") in ("yes", True))
            diff_check = (crossing_difficulty or edge_data.get("crossing_difficulty", "unknown")).lower().strip()
            if is_stairs or diff_check == "high":
                is_step_restricted = True
                limitations.append("Street segment contains stairs or severe crossing barrier; step-free constraint active.")

        # 1. Crime Indicator C(e) (I_crime, Q_crime)
        if has_crime_dataset:
            raw_density = crime_rate_per_km if crime_rate_per_km > 0 else (crime_count / (length_m / 1000.0))
            i_crime = min(round(raw_density / 10.0, 3), 1.0)
            q_crime = 1.0
        else:
            i_crime = self.r_unknown_prior
            q_crime = 0.0
            limitations.append("Crime dataset unmapped; prior assumption applied.")

        # 2. Lighting Indicator L(e) (I_lighting, Q_lighting)
        raw_lit = (lit_status or edge_data.get("lit") or "unmapped")
        if isinstance(raw_lit, list):
            raw_lit = raw_lit[0] if raw_lit else "unmapped"
        raw_lit = str(raw_lit).lower().strip()

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
            i_lighting = 0.70
            q_lighting = 0.80
            limitations.append("Lighting has conflicting municipal vs community observations.")
        else:
            clean_lit = "unmapped"
            i_lighting = self.r_unknown_prior
            q_lighting = 0.0
            limitations.append("Street lighting is unmapped on OpenStreetMap; uncertainty preserved.")

        # 3. Community Feedback Indicator F(e) (I_community, Q_community)
        has_community = bool(edge_data.get("has_community_dataset", False) or community_reports_count > 0)
        if has_community:
            if community_reports_count > 0:
                i_community = min(round(0.35 * community_reports_count, 3), 1.0)
                q_community = 1.0
            else:
                i_community = 0.05
                q_community = 0.70
        else:
            i_community = self.r_unknown_prior
            q_community = 0.0
            limitations.append("Community feedback data is unmapped; uncertainty preserved.")

        # 4. Emergency Facility Access Isolation A(e) (I_assistance, Q_assistance)
        has_assistance = (police_walking_minutes is not None or hospital_walking_minutes is not None)
        if has_assistance:
            t_pol = police_walking_minutes if police_walking_minutes is not None else 999.0
            t_hosp = hospital_walking_minutes if hospital_walking_minutes is not None else 999.0
            min_access_time = min(t_pol, t_hosp)

            if min_access_time <= 5.0:
                i_assistance = 0.10
                q_assistance = 1.0
            elif min_access_time <= 12.0:
                i_assistance = 0.35
                q_assistance = 1.0
            elif min_access_time <= 20.0:
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

        # 5. Street Dog Encounter Indicator D(e) (I_dog, Q_dog)
        dog_rep_list = dog_reports or []
        effective_dog_cnt = dog_incidents_count or len(dog_rep_list)
        has_dog_data = bool(edge_data.get("has_dog_dataset", False) or effective_dog_cnt > 0)

        if has_dog_data:
            if effective_dog_cnt > 0:
                q_dog = 1.0
                severities: List[float] = []
                now = datetime.now(timezone.utc)

                for dr in dog_rep_list:
                    if isinstance(dr, dict):
                        cat = dr.get("subcategory") or dr.get("category", "")
                        enc_type = dr.get("encounter_type", "")
                        is_agg = dr.get("is_aggressive", False)
                        sev_val = dr.get("severity", 0)
                        obs_at = dr.get("encounter_time") or dr.get("observed_at") or dr.get("created_at")
                    else:
                        cat = getattr(dr, "subcategory", None) or getattr(dr, "category", "")
                        enc_type = getattr(dr, "encounter_type", "")
                        is_agg = getattr(dr, "is_aggressive", False)
                        sev_val = getattr(dr, "severity", 0)
                        obs_at = getattr(dr, "encounter_time", None) or getattr(dr, "observed_at", None) or getattr(dr, "created_at", None)

                    if cat in ("dog_bite", "bite") or enc_type == "bite" or sev_val == 5:
                        base_sev = 0.95
                    elif cat in ("dog_aggressive", "aggressive") or enc_type == "aggressive" or is_agg or sev_val >= 4:
                        base_sev = 0.65
                    elif cat in ("dog_group", "group") or enc_type == "group" or sev_val == 3:
                        base_sev = 0.35
                    else:
                        base_sev = 0.05  # Ordinary sighting: informational only

                    # Recency decay weight
                    recency_weight = 1.0
                    if obs_at and base_sev > 0.05:
                        if isinstance(obs_at, str):
                            try:
                                obs_at_dt = datetime.fromisoformat(obs_at.replace("Z", "+00:00"))
                            except Exception:
                                obs_at_dt = now
                        elif isinstance(obs_at, datetime):
                            obs_at_dt = obs_at
                        else:
                            obs_at_dt = now

                        if obs_at_dt.tzinfo is None or obs_at_dt.tzinfo.utcoffset(obs_at_dt) is None:
                            obs_at_dt = obs_at_dt.replace(tzinfo=timezone.utc)

                        age_days = max((now - obs_at_dt).total_seconds() / 86400.0, 0.0)
                        if age_days <= 7.0:
                            recency_weight = 1.0
                        elif age_days <= 30.0:
                            recency_weight = 0.75
                        elif age_days <= 90.0:
                            recency_weight = 0.40
                        else:
                            recency_weight = 0.10

                    severities.append(round(base_sev * recency_weight, 4))

                if severities:
                    max_s = max(severities)
                    cluster_bonus = min(0.05 * (len(severities) - 1), 0.15)
                    i_dog = min(round(max_s + cluster_bonus, 3), 1.0)
                else:
                    i_dog = min(round(0.20 * effective_dog_cnt, 3), 1.0)
            else:
                i_dog = 0.0
                q_dog = 0.60
        else:
            i_dog = self.r_unknown_prior
            q_dog = 0.0
            limitations.append("Street dog encounter data unmapped; uncertainty preserved.")

        # 6. Pedestrian Infrastructure Deficiency Indicator P(e) (I_infra, Q_infra)
        sw_st = sidewalk_status or edge_data.get("sidewalk_status") or edge_data.get("sidewalk") or "unmapped"
        if isinstance(sw_st, list):
            sw_st = sw_st[0] if sw_st else "unmapped"

        cr_st = crossing_status or edge_data.get("crossing_status") or edge_data.get("crossing") or "unmapped"
        if isinstance(cr_st, list):
            cr_st = cr_st[0] if cr_st else "unmapped"

        cr_diff = crossing_difficulty or edge_data.get("crossing_difficulty") or "unknown"
        tac_pav = has_tactile_paving if has_tactile_paving is not None else edge_data.get("has_tactile_paving")
        act_obs = bool(has_active_obstruction or edge_data.get("has_construction_hazard", False))
        wc_acc = wheelchair_accessible or edge_data.get("wheelchair_accessible") or edge_data.get("wheelchair") or "unmapped"

        i_infra, q_infra, infra_limits = PedestrianInfrastructureProcessor.evaluate_infrastructure_deficiency(
            sidewalk_status=str(sw_st),
            crossing_status=str(cr_st),
            crossing_difficulty=str(cr_diff),
            has_tactile_paving=tac_pav,
            wheelchair_accessible=str(wc_acc),
            has_construction_hazard=act_obs,
            r_unknown_prior=self.r_unknown_prior
        )
        limitations.extend(infra_limits)

        # 7. Synthesize Evidence Coverage Q and Observed Adverse Risk R_observed
        # Total effective coverage: Q = sum(w_i * q_i)
        coverage_q = (
            self.w_crime * q_crime +
            self.w_lighting * q_lighting +
            self.w_community * q_community +
            self.w_assistance * q_assistance +
            self.w_dog * q_dog +
            self.w_infrastructure * q_infra
        )
        coverage_q = max(min(round(coverage_q, 4), 1.0), 0.0)

        # Observed Adverse Risk: weighted average over observed indicators
        weighted_observed_sum = (
            self.w_crime * q_crime * i_crime +
            self.w_lighting * q_lighting * i_lighting +
            self.w_community * q_community * i_community +
            self.w_assistance * q_assistance * i_assistance +
            self.w_dog * q_dog * i_dog +
            self.w_infrastructure * q_infra * i_infra
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

        # 8. Generalized Edge Costs with Hard Constraints
        if is_prohibited:
            cost_fastest = float("inf")
            cost_balanced = float("inf")
            cost_safety = float("inf")
            limitations.append("Confirmed pedestrian-prohibited street; excluded from walking paths.")
        elif is_step_restricted:
            cost_fastest = round(traversal_time_s * 500.0, 2)
            cost_balanced = round(traversal_time_s * 500.0, 2)
            cost_safety = round(traversal_time_s * 500.0, 2)
        else:
            cost_fastest = traversal_time_s  # lambda = 0 (strictly minimizes walking time)
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
            dog_indicator=i_dog,
            dog_coverage=q_dog,
            dog_reports_count=effective_dog_cnt,
            infrastructure_indicator=i_infra,
            infrastructure_coverage=q_infra,
            sidewalk_status=str(sw_st),
            crossing_status=str(cr_st),
            crossing_difficulty=str(cr_diff),
            has_tactile_paving=tac_pav,
            has_active_obstruction=act_obs,
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
            departure_period=dep_period,
            is_pedestrian_prohibited=is_prohibited,
            is_step_restricted=is_step_restricted,
            limitations=sorted(list(set(limitations)))
        )


def get_effective_weights(departure_period: str = "daytime") -> Dict[str, float]:
    """Helper returning normalized weights for a given departure period."""
    return SegmentRiskModel(departure_period=departure_period).get_effective_weights()

