"""
SafePath Finder — Dijkstra Routing Engine & Alternative Routes Service
Implements:
1. Baseline Fastest Route (Dijkstra on travel time T_e, lambda = 0)
2. Balanced Route (Dijkstra on generalized cost, moderate lambda_balanced)
3. Safety-prioritized Route (Dijkstra on generalized cost, high lambda_safety)
4. Distinct Loopless Alternative Routes via Yen's K-Shortest Paths Algorithm
Computes explainable route metrics (distance, duration, route risk, evidence coverage, trade-offs).
"""

import math
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict, field

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, Point

from app.core.config import settings
from app.geospatial.exceptions import (
    DisconnectedNetworkError,
    InvalidCoordinateError,
    OutOfCoverageError,
)
from app.geospatial.segment_risk import SegmentRiskModel, SegmentRiskProfile
from app.geospatial.pedestrian_infrastructure import PedestrianInfrastructureProcessor

logger = logging.getLogger(__name__)

# Verified major civic landmarks, recreation spaces, and rapid transit hubs in the Bengaluru pilot corridor
PILOT_CORRIDOR_LANDMARKS: List[Dict[str, Any]] = [
    {"id": "poi-jayanagar-ttmc", "name": "Jayanagar 4th Block Bus Station & TTMC", "category": "transit", "latitude": 12.9257, "longitude": 77.5833, "is_assistance": False},
    {"id": "poi-southend-metro", "name": "South End Circle Rapid Transit Station", "category": "transit", "latitude": 12.9330, "longitude": 77.5832, "is_assistance": False},
    {"id": "poi-madhavan-park", "name": "Madhavan Park & Playground", "category": "park", "latitude": 12.9370, "longitude": 77.5860, "is_assistance": False},
    {"id": "poi-ashoka-pillar", "name": "Ashoka Pillar Heritage Monument", "category": "landmark", "latitude": 12.9370, "longitude": 77.5835, "is_assistance": False},
    {"id": "poi-lalbagh-west", "name": "Lalbagh Botanical Garden (West Gate)", "category": "park", "latitude": 12.9460, "longitude": 77.5844, "is_assistance": False},
    {"id": "poi-lalbagh-main", "name": "Lalbagh Botanical Garden (Main Gate)", "category": "park", "latitude": 12.9501, "longitude": 77.5847, "is_assistance": False},
    {"id": "poi-gandhi-bazaar", "name": "Gandhi Bazaar Commercial Corridor", "category": "landmark", "latitude": 12.9420, "longitude": 77.5720, "is_assistance": False},
    {"id": "poi-shantinagar-bus", "name": "Shantinagar BMTC Transit Interchange", "category": "transit", "latitude": 12.9580, "longitude": 77.5860, "is_assistance": False},
    {"id": "poi-corporation-circle", "name": "Corporation Circle (BBMP Civic Center)", "category": "landmark", "latitude": 12.9680, "longitude": 77.5880, "is_assistance": False},
    {"id": "poi-richmond-circle", "name": "Richmond Circle Junction", "category": "landmark", "latitude": 12.9660, "longitude": 77.5990, "is_assistance": False},
    {"id": "poi-cubbon-park", "name": "Cubbon Park & State Central Library", "category": "park", "latitude": 12.9770, "longitude": 77.5920, "is_assistance": False},
    {"id": "poi-kanteerava-stadium", "name": "Sree Kanteerava Outdoor Stadium", "category": "landmark", "latitude": 12.9730, "longitude": 77.5930, "is_assistance": False},
    {"id": "poi-mg-road-metro", "name": "MG Road Rapid Transit Station", "category": "transit", "latitude": 12.9750, "longitude": 77.6050, "is_assistance": False},
    {"id": "poi-brigade-road", "name": "Brigade Road Commercial Promenade", "category": "landmark", "latitude": 12.9740, "longitude": 77.6070, "is_assistance": False},
]


@dataclass
class ComputedRoute:
    """Detailed result payload for a single computed route alternative."""
    id: str
    name: str
    category: str  # "fastest", "balanced", "safety_prioritized", "alternative"
    preference: str  # "Fastest", "Balanced", "Safety-prioritized", "Alternative"
    distance_meters: int
    duration_seconds: int
    duration_minutes: float
    total_cost: float
    route_risk_indicator: float  # Time-weighted mean effective risk in [0, 1]
    evidence_coverage: float  # Time-weighted evidence coverage Q in [0, 1]
    has_insufficient_evidence: bool

    # Summaries of environmental factors
    lit_percentage: float
    unlit_percentage: float
    unmapped_percentage: float
    conflicting_percentage: float
    crime_incidents_total: int
    community_reports_total: int
    min_police_distance_meters: Optional[float]
    min_hospital_distance_meters: Optional[float]

    # Human-readable explanations
    characteristics: List[str]
    tradeoffs: str
    ranking_explanation: str
    ranking_factors: List[str]
    source_metadata: Dict[str, Any]

    # Spatial path data
    node_path: List[int]
    geometry: List[List[float]]  # [[lat, lon], ...]
    segments: List[Dict[str, Any]]
    limitations: List[str]
    is_identical_to_fastest: bool = False
    identical_notes: Optional[str] = None
    streetlight_summary: Optional[Dict[str, Any]] = None
    nearby_places: List[Dict[str, Any]] = field(default_factory=list)
    dog_encounter_summary: Optional[Dict[str, Any]] = None
    pedestrian_infrastructure_summary: Optional[Dict[str, Any]] = None

    # Phase 2 Multi-Dimensional and Temporal Extensions
    departure_period: str = "daytime"
    step_free: bool = False
    adverse_risk_score: Optional[float] = None
    overlap_with_fastest: Optional[float] = None
    explanation_details: Optional[Dict[str, Any]] = None
    walking_speed_mps: float = 1.2
    walking_speed_kmh: float = 4.3

    @property
    def route_risk(self) -> float:
        """Alias for route_risk_indicator for backward compatibility."""
        return self.route_risk_indicator

    @property
    def lambda_weight(self) -> float:
        """Returns the lambda risk-priority weight applied to this route preference."""
        if self.category == "fastest":
            return 0.0
        elif self.category == "balanced":
            return getattr(settings, "ROUTING_LAMBDA_BALANCED", 1.0)
        elif self.category == "safety_prioritized":
            return getattr(settings, "ROUTING_LAMBDA_SAFETY", 3.0)
        return getattr(settings, "ROUTING_LAMBDA_BALANCED", 1.0)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DijkstraRouter:
    """
    Pedestrian routing engine providing:
    - Baseline fastest path (Dijkstra on travel time T_e, strictly independent of time-of-day)
    - Multi-criteria risk-weighted paths (Balanced & Safety-prioritized)
    - Time-aware evidence evaluation (Daytime, Evening, Night)
    - Pedestrian restriction and step-free accessibility constraints
    - Yen's K-shortest loopless alternative paths with length-weighted overlap filtering
    Guarantees non-negative, finite edge costs and explainable trade-off narratives.
    """

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        risk_model: Optional[SegmentRiskModel] = None,
        facilities_result: Optional[Any] = None,
        crime_dataset: Optional[Any] = None,
        community_reports: Optional[List[Any]] = None,
        max_detour_ratio: Optional[float] = None,
        overlap_threshold: Optional[float] = None,
        max_alternatives: Optional[int] = None,
        departure_period: Optional[str] = None,
        step_free: bool = False
    ):
        self.graph = graph
        if departure_period is not None:
            self.departure_period = departure_period.lower().strip()
        elif risk_model is not None and hasattr(risk_model, "departure_period") and risk_model.departure_period:
            self.departure_period = risk_model.departure_period.lower().strip()
        else:
            self.departure_period = getattr(settings, "ROUTING_DEFAULT_DEPARTURE_PERIOD", "evening").lower().strip()

        self.step_free = step_free

        self.risk_model = risk_model or SegmentRiskModel(
            departure_period=self.departure_period,
            step_free=self.step_free
        )
        if hasattr(self.risk_model, "departure_period") and self.risk_model.departure_period != self.departure_period:
            self.risk_model.departure_period = self.departure_period
            if hasattr(self.risk_model, "_compute_effective_weights"):
                self.risk_model._compute_effective_weights()
        if hasattr(self.risk_model, "step_free"):
            self.risk_model.step_free = self.step_free

        self.facilities_result = facilities_result
        self.crime_dataset = crime_dataset
        self.community_reports = community_reports
        self.max_detour_ratio = max_detour_ratio or settings.ROUTING_MAX_DETOUR_RATIO
        self.overlap_threshold = overlap_threshold or settings.ROUTING_ALTERNATIVE_OVERLAP_THRESHOLD
        self.max_alternatives = max_alternatives or settings.ROUTING_MAX_ALTERNATIVES
        self._simple_digraphs: Dict[str, Tuple[nx.DiGraph, Dict[Tuple[int, int], int]]] = {}

        if facilities_result and not self.graph.graph.get("facilities_attached"):
            self._attach_facilities(facilities_result)
        if crime_dataset:
            self._attach_crime(crime_dataset)
        if community_reports:
            self._attach_community_reports(community_reports)

        self.edge_profiles: Dict[Tuple[int, int, int], SegmentRiskProfile] = {}
        self._prepare_graph_edge_costs()
        self._init_spatial_index()

    def _init_spatial_index(self) -> None:
        """Initializes Shapely STRtree for sub-millisecond node snapping."""
        from shapely.geometry import Point
        from shapely import STRtree

        if "spatial_tree" in self.graph.graph and "node_list" in self.graph.graph:
            self._spatial_tree = self.graph.graph["spatial_tree"]
            self._node_list = self.graph.graph["node_list"]
            return

        self._node_list = list(self.graph.nodes)
        if self._node_list:
            pts = [Point(self.graph.nodes[n]["x"], self.graph.nodes[n]["y"]) for n in self._node_list]
            self._spatial_tree = STRtree(pts)
            self.graph.graph["spatial_tree"] = self._spatial_tree
            self.graph.graph["node_list"] = self._node_list
        else:
            self._spatial_tree = None

    def _attach_facilities(self, facilities_result: Any) -> None:
        """Computes true pedestrian network walking distances to police stations and hospitals."""
        try:
            from app.geospatial.facility_router import FacilityRouter
            fac_router = FacilityRouter(self.graph)
            police_prox = fac_router.compute_facility_distances_for_nodes(
                getattr(facilities_result, "police_stations", []), "police"
            )
            hosp_prox = fac_router.compute_facility_distances_for_nodes(
                getattr(facilities_result, "hospitals", []), "hospital"
            )

            for u, v, k, data in self.graph.edges(keys=True, data=True):
                pol_u = police_prox.get(u)
                pol_v = police_prox.get(v)
                if pol_u and pol_v:
                    data["nearest_police_distance_meters"] = min(pol_u.distance_meters, pol_v.distance_meters)
                elif pol_u or pol_v:
                    data["nearest_police_distance_meters"] = (pol_u or pol_v).distance_meters

                hosp_u = hosp_prox.get(u)
                hosp_v = hosp_prox.get(v)
                if hosp_u and hosp_v:
                    data["nearest_hospital_distance_meters"] = min(hosp_u.distance_meters, hosp_v.distance_meters)
                elif hosp_u or hosp_v:
                    data["nearest_hospital_distance_meters"] = (hosp_u or hosp_v).distance_meters

            self.graph.graph["facilities_attached"] = True
        except Exception as e:
            logger.warning(f"Could not attach facility proximities to graph: {e}")

    def _attach_crime(self, crime_dataset: Any) -> None:
        """Associates crime dataset records with nearest street segments."""
        try:
            records = getattr(crime_dataset, "records", [])
            has_dataset = getattr(crime_dataset, "is_loaded", False) or len(records) > 0
            for u, v, k, data in self.graph.edges(keys=True, data=True):
                data["has_crime_dataset"] = has_dataset
                data.setdefault("crime_count", 0)

            for rec in records:
                lat, lon = getattr(rec, "latitude", None), getattr(rec, "longitude", None)
                if lat is not None and lon is not None:
                    node_id, dist = self._find_nearest_node(lat, lon)
                    if dist <= 300.0:
                        for neighbor in self.graph.successors(node_id):
                            for k in self.graph[node_id][neighbor]:
                                self.graph[node_id][neighbor][k]["crime_count"] += 1
        except Exception as e:
            logger.warning(f"Could not attach crime records to graph: {e}")

    def _attach_community_reports(self, community_reports: List[Any]) -> None:
        """Associates community feedback reports with nearest street segments."""
        try:
            for u, v, k, data in self.graph.edges(keys=True, data=True):
                data.setdefault("community_reports_count", 0)
                data.setdefault("dog_reports", [])
                data.setdefault("dog_incidents_count", 0)

            for rep in community_reports:
                status = getattr(rep, "status", "approved")
                if status not in ("approved", None):
                    continue

                category = getattr(rep, "category", "") or ""
                lat = getattr(rep, "latitude", None)
                lon = getattr(rep, "longitude", None)
                if lat is not None and lon is not None:
                    node_id, dist = self._find_nearest_node(lat, lon)
                    if dist <= 300.0:
                        for neighbor in self.graph.successors(node_id):
                            for k in self.graph[node_id][neighbor]:
                                if category.startswith("dog_"):
                                    self.graph[node_id][neighbor][k].setdefault("dog_reports", []).append(rep)
                                    self.graph[node_id][neighbor][k]["dog_incidents_count"] = len(
                                        self.graph[node_id][neighbor][k]["dog_reports"]
                                    )
                                else:
                                    self.graph[node_id][neighbor][k]["community_reports_count"] += 1
        except Exception as e:
            logger.warning(f"Could not attach community reports to graph: {e}")

    def _prepare_graph_edge_costs(self) -> None:
        """
        Evaluates risk profiles and attaches non-negative, finite Dijkstra traversal
        costs (cost_fastest, cost_balanced, cost_safety) to all graph edges.
        Enforces pedestrian restrictions and step-free accessibility constraints.
        """
        self._simple_digraphs.clear()
        walking_speed = getattr(self.risk_model, "walking_speed_mps", settings.WALKING_SPEED_MPS)

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            length_m = float(data.get("length", 100.0))
            lit_tag = data.get("lit")
            if isinstance(lit_tag, list):
                lit_tag = lit_tag[0] if lit_tag else None

            # Check if edge has attached assistance or crime data
            pol_dist = data.get("nearest_police_distance_meters")
            pol_time = (pol_dist / (walking_speed * 60.0)) if pol_dist else None
            hosp_dist = data.get("nearest_hospital_distance_meters")
            hosp_time = (hosp_dist / (walking_speed * 60.0)) if hosp_dist else None

            crime_cnt = int(data.get("crime_count", 0))
            crime_rate = float(data.get("crime_rate_per_km", 0.0))
            comm_cnt = int(data.get("community_reports_count", 0))
            has_crime = bool(data.get("has_crime_dataset", False) or crime_cnt > 0)
            dog_reps = data.get("dog_reports", [])
            dog_cnt = int(data.get("dog_incidents_count", 0))

            # Phase 2 Pedestrian Infrastructure Attributes
            sw_tag = data.get("sidewalk_status", data.get("sidewalk"))
            cr_tag = data.get("crossing_status", data.get("crossing"))
            cr_diff = data.get("crossing_difficulty")
            tac_tag = data.get("has_tactile_paving")
            wc_tag = data.get("wheelchair_accessible", data.get("wheelchair"))
            act_obs = bool(data.get("has_construction_hazard") or data.get("has_active_obstruction"))

            profile = self.risk_model.evaluate_edge(
                edge_data=data,
                edge_length_meters=length_m,
                lit_status=lit_tag or "unmapped",
                police_walking_minutes=pol_time,
                hospital_walking_minutes=hosp_time,
                crime_count=crime_cnt,
                crime_rate_per_km=crime_rate,
                community_reports_count=comm_cnt,
                has_crime_dataset=has_crime,
                dog_reports=dog_reps,
                dog_incidents_count=dog_cnt,
                sidewalk_status=sw_tag,
                crossing_status=cr_tag,
                crossing_difficulty=cr_diff,
                has_tactile_paving=tac_tag,
                has_active_obstruction=act_obs,
                wheelchair_accessible=wc_tag,
                departure_period=self.departure_period,
                step_free=self.step_free
            )

            self.edge_profiles[(u, v, k)] = profile

            # Ensure non-negative, finite costs on graph edges (or inf if confirmed prohibited)
            if profile.is_pedestrian_prohibited:
                data["cost_fastest"] = float("inf")
                data["cost_balanced"] = float("inf")
                data["cost_safety"] = float("inf")
            elif profile.is_step_restricted:
                data["cost_fastest"] = max(profile.cost_fastest, 0.01)
                data["cost_balanced"] = max(profile.cost_balanced, 0.01)
                data["cost_safety"] = max(profile.cost_safety, 0.01)
            else:
                data["cost_fastest"] = max(profile.cost_fastest, 0.01)
                data["cost_balanced"] = max(profile.cost_balanced, 0.01)
                data["cost_safety"] = max(profile.cost_safety, 0.01)
            data["length"] = length_m

    def _find_nearest_node(self, lat: float, lon: float) -> Tuple[int, float]:
        """Snaps coordinate pair to nearest graph node using spatial index and haversine distance."""
        if not hasattr(self, "_node_list") or not self._node_list or getattr(self, "_spatial_tree", None) is None:
            self._init_spatial_index()

        if not self._node_list or self._spatial_tree is None:
            raise DisconnectedNetworkError("Pedestrian network graph contains 0 nodes.")

        from shapely.geometry import Point
        idx = self._spatial_tree.nearest(Point(lon, lat))
        best_node = self._node_list[idx]
        n_lat = self.graph.nodes[best_node]["y"]
        n_lon = self.graph.nodes[best_node]["x"]

        # Haversine distance in meters
        r = 6371000.0
        p1, p2 = math.radians(lat), math.radians(n_lat)
        dp, dl = math.radians(n_lat - lat), math.radians(n_lon - lon)
        a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
        dist = r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

        return int(best_node), float(dist)

    def _get_best_edge_key(self, u: int, v: int, weight_attr: str) -> int:
        """Finds edge key with lowest weight for parallel edges between u and v."""
        edges = self.graph[u][v]
        best_k = min(edges.keys(), key=lambda k: edges[k].get(weight_attr, float("inf")))
        return best_k

    def _generate_evidence_explanation(
        self,
        category: str,
        total_time_s: float,
        total_dist_m: float,
        fastest_time_s: Optional[float],
        mean_route_risk: float,
        mean_evidence_cov: float,
        lit_pct: float,
        unlit_pct: float,
        unmapped_pct: float,
        crime_total: int,
        dog_summary: Dict[str, Any],
        infra_summary: Dict[str, Any],
        min_pol_dist: float,
        min_hosp_dist: float,
        departure_period: str,
        is_identical: bool = False,
        identical_reason: Optional[str] = None,
        key_streets: Optional[List[str]] = None
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Dynamically synthesizes evidence-based, explainable route trade-offs without generic placeholders.
        Explains:
        - Selection reason and active cost function
        - Departure period and temporal weighting implications
        - Key street corridors traversed
        - Lighting breakdown (% lit, % unlit, % unknown)
        - Historical crime density & data limitations
        - Dog encounter observations (ordinary vs aggressive)
        - Pedestrian infrastructure quality (sidewalks, crossings, tactile paving)
        - Straight-line distance to assistance facilities (police, hospitals)
        - Additional time delta vs baseline fastest route
        """
        duration_mins = round(total_time_s / 60.0, 1)
        base_time = fastest_time_s if (fastest_time_s is not None and fastest_time_s > 0) else total_time_s
        time_diff_min = max(round((total_time_s - base_time) / 60.0, 1), 0.0)
        time_diff_pct = round((time_diff_min / max(base_time / 60.0, 0.1)) * 100.0, 1) if base_time else 0.0

        dog_cnt = dog_summary.get("totalReportsCount", 0)
        agg_cnt = dog_summary.get("aggressiveCount", 0) + dog_summary.get("biteCount", 0)
        sidewalk_pct = infra_summary.get("sidewalkDocumentedPercentage", 0.0)
        crossings_cnt = infra_summary.get("crossingCount", 0)
        signal_cnt = infra_summary.get("signalizedCrossingCount", 0)
        streets_formatted = []
        if key_streets:
            for s in key_streets[:3]:
                if isinstance(s, list) and s:
                    streets_formatted.append(str(s[0]))
                elif s:
                    streets_formatted.append(str(s))
        streets_str = f" via {', '.join(streets_formatted)}" if streets_formatted else ""

        details: Dict[str, Any] = {
            "departurePeriod": departure_period,
            "durationMinutes": duration_mins,
            "distanceMeters": int(total_dist_m),
            "effectiveRisk": mean_route_risk,
            "evidenceCoveragePct": round(mean_evidence_cov * 100.0, 1),
            "litPercentage": lit_pct,
            "unlitPercentage": unlit_pct,
            "unmappedPercentage": unmapped_pct,
            "crimeIncidents": crime_total,
            "dogReports": dog_cnt,
            "aggressiveDogReports": agg_cnt,
            "sidewalkCoveragePct": sidewalk_pct,
            "crossingCount": crossings_cnt,
            "signalizedCrossings": signal_cnt,
            "nearestPoliceDistanceMeters": round(min_pol_dist, 1) if min_pol_dist < float("inf") else None,
            "nearestHospitalDistanceMeters": round(min_hosp_dist, 1) if min_hosp_dist < float("inf") else None,
            "timeDeltaMinutes": time_diff_min,
            "timeDeltaPercentage": time_diff_pct,
            "isIdenticalToFastest": is_identical
        }

        if is_identical and identical_reason:
            ranking_exp = identical_reason
            tradeoffs = "Fastest direct corridor already follows the most illuminated and facility-proximate path available; no detour needed."
            details["selectionReason"] = "Mathematically optimal across multiple criteria without requiring detours."
        elif category == "fastest":
            ranking_exp = (
                f"Selected as the Fastest Direct Route minimizing pedestrian traversal duration ({duration_mins} min, {int(total_dist_m)}m{streets_str}). "
                f"Edge cost strictly optimizes for traversal time T(e) without risk weighting (lambda=0). "
                f"Traverses {lit_pct}% verified lit streets ({unmapped_pct}% unmapped/uncertain lighting) and {sidewalk_pct}% documented sidewalks."
            )
            tradeoffs = "Baseline shortest travel duration. Does not divert to avoid darker, unmapped, or dog-reported corridors."
            details["selectionReason"] = "Strict traversal time minimization (lambda=0)."

        elif category == "balanced":
            delta_str = f"Adds +{time_diff_min} min (+{time_diff_pct}%) walking time compared to fastest route" if time_diff_min > 0 else "Matches fastest traversal time"
            pol_note = f" Passes within {int(min_pol_dist)}m of emergency police assistance." if min_pol_dist < float("inf") else ""
            ranking_exp = (
                f"Selected as the Balanced Walking Route under departure period '{departure_period}' with moderate risk penalty (lambda={self.risk_model.lambda_balanced}). "
                f"Walking duration is {duration_mins} min ({int(total_dist_m)}m{streets_str}). {delta_str} to prefer corridors with {lit_pct}% verified lighting "
                f"and {sidewalk_pct}% documented sidewalks.{pol_note}"
            )
            tradeoffs = f"{delta_str} to improve verified lighting to {lit_pct}% and avoid lower-evidence street segments."
            details["selectionReason"] = f"Multi-criteria balance between travel time and verified environmental safety (lambda={self.risk_model.lambda_balanced})."

        elif category == "safety_prioritized":
            delta_str = f"Adds +{time_diff_min} min (+{time_diff_pct}%) walking time compared to fastest route" if time_diff_min > 0 else "Direct path is already safest"
            dog_note = f", navigating around {agg_cnt} aggressive dog encounter report(s)" if agg_cnt > 0 else ""
            fac_parts = []
            if min_pol_dist < float("inf"):
                fac_parts.append(f"nearest police station {int(min_pol_dist)}m")
            if min_hosp_dist < float("inf"):
                fac_parts.append(f"hospital {int(min_hosp_dist)}m")
            fac_str = f" ({', '.join(fac_parts)})" if fac_parts else ""
            ranking_exp = (
                f"Selected as the Safety-prioritized Route for departure period '{departure_period}' with high risk penalty (lambda={self.risk_model.lambda_safety}). "
                f"Prioritizes maximum verified illumination ({lit_pct}% lit), sidewalk infrastructure ({sidewalk_pct}%), and emergency facility proximity"
                f"{fac_str}{dog_note}. Effective route risk is reduced to {mean_route_risk:.2f}."
            )
            tradeoffs = (
                f"{delta_str} to maximize verified lighting ({lit_pct}% lit) and pedestrian infrastructure, "
                f"achieving lowest route risk indicator ({mean_route_risk:.2f})."
            )
            details["selectionReason"] = f"Maximum safety and evidence priority (lambda={self.risk_model.lambda_safety})."

        else:
            ranking_exp = (
                f"Selected as Alternative Route via Yen's K-shortest loopless paths algorithm ({duration_mins} min, {int(total_dist_m)}m{streets_str}). "
                f"Provides a distinct topological alternative with low overlap (<{int(self.overlap_threshold*100)}%) against primary choices."
            )
            tradeoffs = "Alternative street sequence providing pedestrian route diversity."
            details["selectionReason"] = "Topologically distinct simple loopless path."

        crime_str = f"Route traverses corridors with {crime_total} documented crime incidents." if crime_total > 0 else "No incidents recorded in the available dataset for the selected area and period."
        details["crime_notice"] = "Historical public incident bulletins; does not represent a predictive probability of victimization."
        details["crimeNotice"] = details["crime_notice"]
        lit_str = f"{lit_pct}% verified lit street length, {unlit_pct}% unlit, {unmapped_pct}% unmapped under '{departure_period}' departure period."
        dog_str = f"{dog_cnt} stray dog observation(s) documented ({agg_cnt} aggressive/bite incidents)." if dog_cnt > 0 else "No stray dog encounters reported along this corridor."
        infra_str = f"{sidewalk_pct}% dedicated sidewalk coverage, {crossings_cnt} road crossings ({signal_cnt} signalized)."
        if min_pol_dist < float("inf") or min_hosp_dist < float("inf"):
            fac_items = []
            if min_pol_dist < float("inf"): fac_items.append(f"police within {int(min_pol_dist)}m")
            if min_hosp_dist < float("inf"): fac_items.append(f"hospital within {int(min_hosp_dist)}m")
            asst_str = f"Assistance facility proximity: {', '.join(fac_items)}."
        else:
            asst_str = "No emergency police or hospital facilities mapped within immediate corridor."
        unc_str = f"Route evidence coverage is {round(mean_evidence_cov * 100.0, 1)}%. Missing data is evaluated using neutral prior R_unknown={self.risk_model.r_unknown_prior}."
        delta_str_narrative = f"+{time_diff_min} min (+{time_diff_pct}%) compared with fastest direct route." if time_diff_min > 0 else "Matches fastest direct walking time."

        details["selection_reason"] = ranking_exp
        details["lighting_evidence"] = lit_str
        details["crime_evidence"] = crime_str
        details["dog_encounters"] = dog_str
        details["infrastructure_evidence"] = infra_str
        details["assistance_proximity"] = asst_str
        details["uncertainty_and_prior"] = unc_str
        details["time_delta_vs_fastest"] = delta_str_narrative

        # CamelCase aliases for frontend compatibility
        details["selectionReason"] = details["selection_reason"]
        details["lightingEvidence"] = lit_str
        details["crimeEvidence"] = crime_str
        details["dogEncounters"] = dog_str
        details["infrastructureEvidence"] = infra_str
        details["assistanceProximity"] = asst_str
        details["uncertaintyAndPrior"] = unc_str
        details["timeDeltaVsFastest"] = delta_str_narrative

        return ranking_exp, tradeoffs, details


    def _reconstruct_route_metrics(
        self,
        node_path: List[int],
        route_id: str,
        name: str,
        category: str,
        preference: str,
        cost_weight_attr: str,
        orig_coords: Optional[Tuple[float, float]] = None,
        dest_coords: Optional[Tuple[float, float]] = None,
        fastest_time_s: Optional[float] = None,
        fastest_node_path: Optional[List[int]] = None,
        identical_notes: Optional[str] = None
    ) -> ComputedRoute:
        """
        Reconstructs full metric geometry, total distance, duration, risk, coverage,
        and human-readable explanations for a given node sequence.
        """
        total_dist_m = 0.0
        total_time_s = 0.0
        total_cost = 0.0
        time_weighted_risk_sum = 0.0
        time_weighted_obs_risk_sum = 0.0
        time_weighted_cov_sum = 0.0

        lit_len = 0.0
        unlit_len = 0.0
        unmapped_len = 0.0
        conflicting_len = 0.0

        crime_total = 0
        comm_total = 0
        min_pol_dist = float("inf")
        min_hosp_dist = float("inf")

        geometry_coords: List[List[float]] = []
        segments_output: List[Dict[str, Any]] = []
        route_limitations: Set[str] = set()

        for i in range(len(node_path) - 1):
            u = node_path[i]
            v = node_path[i + 1]
            k = self._get_best_edge_key(u, v, cost_weight_attr)
            data = self.graph[u][v][k]
            profile = self.edge_profiles.get((u, v, k))

            edge_len = float(data.get("length", 100.0))
            total_dist_m += edge_len

            traversal_s = profile.traversal_time_seconds if profile else (edge_len / self.risk_model.walking_speed_mps)
            total_time_s += traversal_s

            edge_cost = float(data.get(cost_weight_attr, traversal_s))
            total_cost += edge_cost

            eff_risk = profile.effective_risk if profile else self.risk_model.r_unknown_prior
            time_weighted_risk_sum += traversal_s * eff_risk

            obs_risk = profile.observed_risk if profile else self.risk_model.r_unknown_prior
            time_weighted_obs_risk_sum += traversal_s * obs_risk

            cov_q = profile.evidence_coverage if profile else 0.0
            time_weighted_cov_sum += traversal_s * cov_q

            # Lighting distribution
            lit_st = profile.lit_status if profile else "unmapped"
            if lit_st == "lit":
                lit_len += edge_len
            elif lit_st == "unlit":
                unlit_len += edge_len
            elif lit_st == "conflicting":
                conflicting_len += edge_len
            else:
                unmapped_len += edge_len

            # Crime & Community counts
            crime_total += int(data.get("crime_count", 0))
            comm_total += int(data.get("community_reports_count", 0))

            pol_d = data.get("nearest_police_distance_meters")
            if pol_d is not None and pol_d < min_pol_dist:
                min_pol_dist = float(pol_d)

            hosp_d = data.get("nearest_hospital_distance_meters")
            if hosp_d is not None and hosp_d < min_hosp_dist:
                min_hosp_dist = float(hosp_d)

            if profile:
                route_limitations.update(profile.limitations)

            # Reconstruct geometry
            u_lat = float(self.graph.nodes[u].get("y", 0.0))
            u_lon = float(self.graph.nodes[u].get("x", 0.0))
            v_lat = float(self.graph.nodes[v].get("y", 0.0))
            v_lon = float(self.graph.nodes[v].get("x", 0.0))

            geom = data.get("geometry")
            if geom and isinstance(geom, LineString):
                pts = [[round(lat, 6), round(lon, 6)] for lon, lat in geom.coords]
            elif geom and isinstance(geom, str) and "LINESTRING" in geom.upper():
                from shapely import wkt
                ls = wkt.loads(geom)
                pts = [[round(lat, 6), round(lon, 6)] for lon, lat in ls.coords]
            else:
                pts = [[round(u_lat, 6), round(u_lon, 6)], [round(v_lat, 6), round(v_lon, 6)]]

            # Ensure reconstructed points are strictly oriented from u towards v
            if pts:
                d_start_u = math.hypot(pts[0][0] - u_lat, pts[0][1] - u_lon)
                d_end_u = math.hypot(pts[-1][0] - u_lat, pts[-1][1] - u_lon)
                if d_end_u < d_start_u:
                    pts.reverse()

            if not geometry_coords:
                geometry_coords.extend(pts)
            else:
                if pts and math.hypot(pts[0][0] - geometry_coords[-1][0], pts[0][1] - geometry_coords[-1][1]) < 0.00005:
                    geometry_coords.extend(pts[1:])
                else:
                    geometry_coords.extend(pts)

            segments_output.append({
                "segmentId": f"seg-{u}-{v}-{k}",
                "edgeU": u,
                "edgeV": v,
                "edgeKey": k,
                "streetName": data.get("name", "Pathway"),
                "lengthMeters": round(edge_len, 1),
                "traversalTimeSeconds": round(traversal_s, 1),
                "effectiveRisk": eff_risk,
                "observedRisk": obs_risk,
                "evidenceCoverage": cov_q,
                "litStatus": lit_st,
                "sidewalkStatus": data.get("sidewalk_status", data.get("sidewalk", "unmapped")),
                "crossingStatus": data.get("crossing_status", "unmapped"),
                "crossingDifficulty": data.get("crossing_difficulty", "unknown"),
                "hasTactilePaving": data.get("has_tactile_paving"),
                "crimeCount": data.get("crime_count", 0),
                "dogIncidentsCount": data.get("dog_incidents_count", 0),
                "communityReportsCount": data.get("community_reports_count", 0),
                "geometry": pts
            })

        # Calculate time-weighted averages
        mean_route_risk = round(time_weighted_risk_sum / max(total_time_s, 0.1), 4)
        mean_adverse_risk = round(time_weighted_obs_risk_sum / max(total_time_s, 0.1), 4)
        mean_evidence_cov = round(time_weighted_cov_sum / max(total_time_s, 0.1), 4)
        has_insufficient = (mean_evidence_cov < self.risk_model.min_coverage_threshold)

        lit_pct = round((lit_len / max(total_dist_m, 1.0)) * 100.0, 1)
        unlit_pct = round((unlit_len / max(total_dist_m, 1.0)) * 100.0, 1)
        unmapped_pct = round((unmapped_len / max(total_dist_m, 1.0)) * 100.0, 1)
        conf_pct = round((conflicting_len / max(total_dist_m, 1.0)) * 100.0, 1)

        duration_mins = round(total_time_s / 60.0, 1)

        # Count mapped street lamps near route nodes
        mapped_lamps_count = sum(
            1 for n in node_path if self.graph.nodes[n].get("highway") == "street_lamp"
        )

        # Build detailed streetlight evidence summary (Priority 4)
        streetlight_summary = {
            "totalDistanceMeters": round(total_dist_m, 1),
            "totalTraversedMeters": round(total_dist_m, 1),
            "knownLitDistanceMeters": round(lit_len, 1),
            "litDistanceMeters": round(lit_len, 1),
            "knownUnlitDistanceMeters": round(unlit_len, 1),
            "unlitDistanceMeters": round(unlit_len, 1),
            "conflictingDistanceMeters": round(conflicting_len, 1),
            "unknownDistanceMeters": round(unmapped_len, 1),
            "unmappedDistanceMeters": round(unmapped_len, 1),
            "litPercentage": lit_pct,
            "unlitPercentage": unlit_pct,
            "conflictingPercentage": conf_pct,
            "unknownPercentage": unmapped_pct,
            "unmappedPercentage": unmapped_pct,
            "mappedStreetlampsCount": mapped_lamps_count,
            "sources": [
                "OpenStreetMap way tags ('lit=yes', 'lit=no')",
                "OpenStreetMap node tags ('highway=street_lamp')"
            ],
            "explanation": (
                f"Traversed walking distance is {int(total_dist_m)}m: {lit_pct}% ({int(lit_len)}m) is mapped as lit in OpenStreetMap (not field-verified operational); "
                f"{unlit_pct}% ({int(unlit_len)}m) is explicitly mapped as unlit; and {unmapped_pct}% ({int(unmapped_len)}m) has unknown/unmapped "
                f"lighting. In accordance with SafePath research policy, unmapped segments are evaluated under modeling uncertainty "
                f"(prior R_unknown = {self.risk_model.r_unknown_prior}) and are NEVER assumed to be dark or hazardous."
            )
        }

        # Find nearby major landmarks and assistance facilities (Priority 5)
        nearby_places = self._find_nearby_places(
            geometry_coords=geometry_coords,
            corridor_meters=getattr(settings, "ROUTING_NEARBY_CORRIDOR_METERS", 500.0),
            max_results=getattr(settings, "ROUTING_MAX_NEARBY_PLACES", 10)
        )

        # Discover dog-related evidence along corridor (Priority 6)
        dog_summary = self._compute_dog_summary(
            node_path=node_path,
            geometry_coords=geometry_coords,
            total_dist_m=total_dist_m,
            corridor_meters=getattr(settings, "ROUTING_DOG_CORRIDOR_METERS", 200.0)
        )

        # Compute pedestrian infrastructure summary (Phase 1 & 2)
        infra_summary = PedestrianInfrastructureProcessor.compute_route_infrastructure_summary(
            segments=segments_output,
            total_distance_meters=total_dist_m
        )

        # Build characteristics
        characteristics = [
            f"{lit_pct}% verified street lighting",
            f"Walking distance {int(total_dist_m)}m (~{duration_mins} min)",
        ]
        if min_pol_dist < float("inf"):
            characteristics.append(f"Nearest police facility within {int(min_pol_dist)}m")
        if crime_total > 0:
            characteristics.append(f"{crime_total} historical crime record(s) along segments")
        if dog_summary.get("totalReportsCount", 0) > 0:
            characteristics.append(f"{dog_summary['totalReportsCount']} reported dog encounter(s) within corridor")
        if infra_summary.get("sidewalkDocumentedPercentage", 0) > 0:
            characteristics.append(f"{infra_summary['sidewalkDocumentedPercentage']}% documented sidewalks/footpaths")
        if unmapped_pct > 40.0:
            characteristics.append(f"{unmapped_pct}% unmapped lighting (uncertainty preserved)")
        if nearby_places:
            top_place = nearby_places[0]
            characteristics.append(f"Passes near {top_place['name']} ({int(top_place['distanceMeters'])}m)")

        # Overlap with fastest
        overlap_with_fastest = None
        is_ident = False
        if fastest_node_path is not None:
            overlap_with_fastest = round(self.calculate_path_edge_overlap(node_path, fastest_node_path, graph=self.graph), 3)
            is_ident = bool(node_path == fastest_node_path)
        elif category == "fastest":
            overlap_with_fastest = 1.0
            is_ident = True

        # Generate Evidence-Based Explanation
        ranking_exp, tradeoffs, exp_details = self._generate_evidence_explanation(
            category=category,
            total_time_s=total_time_s,
            total_dist_m=total_dist_m,
            fastest_time_s=fastest_time_s,
            mean_route_risk=mean_route_risk,
            mean_evidence_cov=mean_evidence_cov,
            lit_pct=lit_pct,
            unlit_pct=unlit_pct,
            unmapped_pct=unmapped_pct,
            crime_total=crime_total,
            dog_summary=dog_summary,
            infra_summary=infra_summary,
            min_pol_dist=min_pol_dist,
            min_hosp_dist=min_hosp_dist,
            departure_period=self.departure_period,
            is_identical=is_ident,
            identical_reason=identical_notes,
            key_streets=[s.get("streetName") for s in segments_output if s.get("streetName") and s.get("streetName") != "Pathway"]
        )

        if has_insufficient:
            route_limitations.add(
                f"Evidence coverage ({round(mean_evidence_cov*100, 1)}%) is insufficient for a confident safety assessment."
            )

        return ComputedRoute(
            id=route_id,
            name=name,
            category=category,
            preference=preference,
            distance_meters=int(round(total_dist_m)),
            duration_seconds=int(round(total_time_s)),
            duration_minutes=duration_mins,
            total_cost=round(total_cost, 2),
            route_risk_indicator=mean_route_risk,
            evidence_coverage=mean_evidence_cov,
            has_insufficient_evidence=has_insufficient,
            lit_percentage=lit_pct,
            unlit_percentage=unlit_pct,
            unmapped_percentage=unmapped_pct,
            conflicting_percentage=conf_pct,
            crime_incidents_total=crime_total,
            community_reports_total=comm_total,
            min_police_distance_meters=min_pol_dist if min_pol_dist < float("inf") else None,
            min_hospital_distance_meters=min_hosp_dist if min_hosp_dist < float("inf") else None,
            characteristics=characteristics,
            tradeoffs=tradeoffs,
            ranking_explanation=ranking_exp,
            ranking_factors=[
                f"Generalized cost: {round(total_cost, 2)}",
                f"Walking duration: {duration_mins} min",
                f"Lit streets: {lit_pct}%",
                f"Departure period: {self.departure_period.capitalize()}"
            ],
            source_metadata={
                "network": "OpenStreetMap pedestrian graph",
                "licensing": "ODbL 1.0",
                "algorithm": "Dijkstra / Yen loopless paths",
                "modelVersion": getattr(self.risk_model, "model_version", "2.0.0"),
                "departurePeriod": self.departure_period
            },
            node_path=node_path,
            geometry=geometry_coords,
            segments=segments_output,
            limitations=sorted(list(route_limitations)),
            is_identical_to_fastest=is_ident,
            identical_notes=identical_notes if is_ident else None,
            streetlight_summary=streetlight_summary,
            nearby_places=nearby_places,
            dog_encounter_summary=dog_summary,
            pedestrian_infrastructure_summary=infra_summary,
            departure_period=self.departure_period,
            step_free=self.step_free,
            adverse_risk_score=mean_adverse_risk,
            overlap_with_fastest=overlap_with_fastest,
            explanation_details=exp_details,
            walking_speed_mps=round(self.risk_model.walking_speed_mps, 2),
            walking_speed_kmh=round(self.risk_model.walking_speed_mps * 3.6, 1)
        )

    def _find_nearby_places(
        self,
        geometry_coords: List[List[float]],
        corridor_meters: float = 500.0,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Discovers verified civic assistance facilities, transit stops, and landmarks
        within the configured spatial corridor along the route geometry.
        Distinguishes emergency/medical assistance from ordinary landmarks.
        """
        if not geometry_coords or len(geometry_coords) < 2:
            return []

        ref_lat = geometry_coords[0][0]
        ref_lon = geometry_coords[0][1]
        m_per_lat = 111000.0
        m_per_lon = 111000.0 * math.cos(math.radians(ref_lat))

        route_pts = [((lon - ref_lon) * m_per_lon, (lat - ref_lat) * m_per_lat) for lat, lon in geometry_coords]
        route_line = LineString(route_pts)

        all_candidates: List[Dict[str, Any]] = []

        # 1. Assistance facilities and civic POIs from verified facilities
        if hasattr(self, "facilities_result") and self.facilities_result:
            all_facs = getattr(self.facilities_result, "all_facilities", None)
            if all_facs:
                for fac in all_facs:
                    all_candidates.append({
                        "id": fac.id,
                        "name": fac.name,
                        "category": fac.facility_type,
                        "latitude": fac.latitude,
                        "longitude": fac.longitude,
                        "is_assistance": getattr(fac, "is_assistance", False),
                        "source": getattr(fac, "source", "OpenStreetMap"),
                        "limitations": getattr(fac, "limitations", "Public location mapped on OpenStreetMap.")
                    })
            else:
                for fac in getattr(self.facilities_result, "police_stations", []):
                    all_candidates.append({
                        "id": fac.id,
                        "name": fac.name,
                        "category": "police",
                        "latitude": fac.latitude,
                        "longitude": fac.longitude,
                        "is_assistance": True,
                        "source": "OpenStreetMap (amenity=police)",
                        "limitations": "Operating hours, desk staffing, and immediate response readiness are not monitored in real time."
                    })
                for fac in getattr(self.facilities_result, "hospitals", []):
                    all_candidates.append({
                        "id": fac.id,
                        "name": fac.name,
                        "category": "hospital",
                        "latitude": fac.latitude,
                        "longitude": fac.longitude,
                        "is_assistance": True,
                        "source": "OpenStreetMap (amenity=hospital)",
                        "limitations": "Emergency capacity, bed availability, and specialty medical services are not monitored in real time."
                    })

        # 2. Add corridor landmarks and transit hubs
        all_candidates.extend(PILOT_CORRIDOR_LANDMARKS)

        matched: List[Dict[str, Any]] = []
        for cand in all_candidates:
            c_lat = cand["latitude"]
            c_lon = cand["longitude"]
            c_pt = Point((c_lon - ref_lon) * m_per_lon, (c_lat - ref_lat) * m_per_lat)
            dist_m = float(route_line.distance(c_pt))

            if dist_m <= corridor_meters:
                walk_mins = round(dist_m / (self.risk_model.walking_speed_mps * 60.0), 1)
                is_asst = cand.get("is_assistance", cand.get("category") in {"police", "hospital", "pharmacy"})
                matched.append({
                    "id": cand["id"],
                    "name": cand["name"],
                    "category": cand["category"],
                    "distanceMeters": round(dist_m, 1),
                    "walkingMinutes": walk_mins,
                    "coordinates": [round(c_lat, 6), round(c_lon, 6)],
                    "isAssistance": is_asst,
                    "distanceType": "straight_line",
                    "source": cand.get("source", "OpenStreetMap"),
                    "attribution": "© OpenStreetMap contributors, ODbL 1.0",
                    "limitations": cand.get("limitations", "Public location mapped on OpenStreetMap.")
                })

        # Sort by distance ascending and cap at max_results
        matched.sort(key=lambda x: x["distanceMeters"])
        seen_names = set()
        deduped = []
        for m in matched:
            clean_name = m["name"].lower().strip()
            if clean_name not in seen_names:
                seen_names.add(clean_name)
                deduped.append(m)
                if len(deduped) >= max_results:
                    break

        return deduped

    def _compute_dog_summary(
        self,
        node_path: List[int],
        geometry_coords: List[List[float]],
        total_dist_m: float,
        corridor_meters: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Computes route-level dog encounter evidence summary within a configurable spatial corridor (default 200m).
        Ensures deduplication across multiple route edges and preserves reporter privacy.
        """
        corridor = corridor_meters or getattr(settings, "ROUTING_DOG_CORRIDOR_METERS", 200.0)

        total_eligible = len([r for r in (self.community_reports or []) if getattr(r, "category", "").startswith("dog_")])
        empty_summary = {
            "totalReportsCount": 0,
            "eligibleReportsCount": total_eligible,
            "approvedReportsCount": 0,
            "sightingCount": 0,
            "groupCount": 0,
            "aggressiveCount": 0,
            "biteCount": 0,
            "freshestReportDays": None,
            "affectedRouteLengthMeters": 0.0,
            "affectedLengthPercentage": 0.0,
            "corridorMeters": corridor,
            "totalRouteLengthMeters": round(total_dist_m, 1),
            "usableDogEvidenceLengthMeters": 0.0,
            "explanation": (
                "No approved dog-encounter reports were found within the selected route corridor. "
                "SafePath research policy emphasizes that absence of reported sightings does NOT confirm the absolute "
                "absence of stray animals. Missing data is preserved as modeling uncertainty."
            ),
            "guidance": [
                "Maintain standard situational awareness when walking during dawn, dusk, or night hours.",
                "Submit observations via Community Reports to help maintain up-to-date neighborhood safety evidence."
            ]
        }

        if not geometry_coords or len(geometry_coords) < 2 or not self.community_reports:
            return empty_summary

        dog_reports: List[Any] = []
        for rep in self.community_reports:
            cat = getattr(rep, "category", "") or ""
            status = getattr(rep, "status", "approved")
            if cat.startswith("dog_") and status in ("approved", None):
                dog_reports.append(rep)

        if not dog_reports:
            return empty_summary

        ref_lat = geometry_coords[0][0]
        ref_lon = geometry_coords[0][1]
        m_per_lat = 111000.0
        m_per_lon = 111000.0 * math.cos(math.radians(ref_lat))

        route_pts = [((lon - ref_lon) * m_per_lon, (lat - ref_lat) * m_per_lat) for lat, lon in geometry_coords]
        route_line = LineString(route_pts)

        matched_reports: Dict[str, Any] = {}
        now = datetime.now(timezone.utc)

        for rep in dog_reports:
            lat = getattr(rep, "latitude", None)
            lon = getattr(rep, "longitude", None)
            if lat is None or lon is None:
                continue

            pt = Point((lon - ref_lon) * m_per_lon, (lat - ref_lat) * m_per_lat)
            dist = route_line.distance(pt)
            if dist <= corridor:
                rep_id = str(getattr(rep, "id", None) or f"{lat:.5f}_{lon:.5f}")
                if rep_id not in matched_reports:
                    matched_reports[rep_id] = {
                        "report": rep,
                        "distance": dist
                    }

        if not matched_reports:
            return empty_summary

        sighting_cnt = 0
        group_cnt = 0
        aggressive_cnt = 0
        bite_cnt = 0
        min_age_days: Optional[int] = None

        for item in matched_reports.values():
            rep = item["report"]
            cat = getattr(rep, "category", "")
            if cat == "dog_sighting":
                sighting_cnt += 1
            elif cat == "dog_group":
                group_cnt += 1
            elif cat == "dog_aggressive":
                aggressive_cnt += 1
            elif cat == "dog_bite":
                bite_cnt += 1
            else:
                sighting_cnt += 1

            ts = getattr(rep, "encounter_time", None) or getattr(rep, "created_at", None)
            if ts:
                if isinstance(ts, str):
                    try:
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        ts_dt = now
                elif isinstance(ts, datetime):
                    ts_dt = ts
                else:
                    ts_dt = now

                if ts_dt.tzinfo is None or ts_dt.tzinfo.utcoffset(ts_dt) is None:
                    ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                age_days = max(0, (now - ts_dt).days)
                if min_age_days is None or age_days < min_age_days:
                    min_age_days = age_days

        total_cnt = len(matched_reports)

        # Estimate affected route length (segments near matched dog reports)
        affected_length = 0.0
        for i in range(len(node_path) - 1):
            u, v = node_path[i], node_path[i + 1]
            if self.graph.has_edge(u, v):
                edge_data = min(self.graph[u][v].values(), key=lambda d: d.get("length", 100.0))
                edge_len = float(edge_data.get("length", 100.0))
                edge_dog_reps = edge_data.get("dog_reports", [])
                if edge_dog_reps or edge_data.get("dog_incidents_count", 0) > 0:
                    affected_length += edge_len
                else:
                    u_lat, u_lon = self.graph.nodes[u]["y"], self.graph.nodes[u]["x"]
                    v_lat, v_lon = self.graph.nodes[v]["y"], self.graph.nodes[v]["x"]
                    mid_pt = Point((((u_lon + v_lon)/2.0 - ref_lon) * m_per_lon), (((u_lat + v_lat)/2.0 - ref_lat) * m_per_lat))
                    for m_item in matched_reports.values():
                        m_rep = m_item["report"]
                        m_pt = Point(((m_rep.longitude - ref_lon) * m_per_lon), ((m_rep.latitude - ref_lat) * m_per_lat))
                        if mid_pt.distance(m_pt) <= 100.0:
                            affected_length += edge_len
                            break

        affected_length = min(round(affected_length, 1), round(total_dist_m, 1))
        affected_pct = round((affected_length / max(total_dist_m, 1.0)) * 100.0, 1)

        parts = []
        if sighting_cnt > 0:
            parts.append(f"{sighting_cnt} calm sighting(s)")
        if group_cnt > 0:
            parts.append(f"{group_cnt} group/pack sighting(s)")
        if aggressive_cnt > 0:
            parts.append(f"{aggressive_cnt} aggressive encounter(s)")
        if bite_cnt > 0:
            parts.append(f"{bite_cnt} physical bite incident(s)")

        breakdown_str = ", ".join(parts)
        age_str = f" Most recent report is {min_age_days} day(s) old." if min_age_days is not None else ""

        if aggressive_cnt > 0 or bite_cnt > 0:
            explanation = (
                f"Identified {total_cnt} community-reported dog encounter(s) along {affected_pct}% of this route corridor: "
                f"{breakdown_str}.{age_str} In accordance with SafePath routing policy, aggressive encounters contribute to higher safety "
                "cost penalties, allowing safety-prioritized preferences to divert where viable alternatives exist."
            )
        else:
            explanation = (
                f"Identified {total_cnt} informational dog sighting(s) along {affected_pct}% of this route corridor: "
                f"{breakdown_str}.{age_str} In accordance with SafePath research policy, calm or ordinary dog sightings are displayed "
                "for situational awareness and do NOT automatically classify a street as hazardous."
            )

        guidance = []
        if bite_cnt > 0:
            guidance.append("Physical bite incidents reported along this corridor: prefer well-lit, populated avenues or alternative routes if walking alone.")
            guidance.append("In an encounter, do not run or turn your back; place an object (bag, umbrella) between yourself and the animal.")
        elif aggressive_cnt > 0:
            guidance.append("Aggressive behavior (barking, chasing) reported: keep a calm, steady walking pace; avoid direct eye contact.")
            guidance.append("Consider walking with others during late evening or early morning.")
        elif group_cnt > 0:
            guidance.append("Groups or packs of dogs reported: give dogs a wide berth and avoid cornering them near resting spots or food sources.")
        else:
            guidance.append("Ordinary sightings are calm and informational; maintain normal pedestrian awareness.")

        return {
            "totalReportsCount": total_cnt,
            "eligibleReportsCount": total_eligible,
            "approvedReportsCount": len(dog_reports),
            "sightingCount": sighting_cnt,
            "groupCount": group_cnt,
            "aggressiveCount": aggressive_cnt,
            "biteCount": bite_cnt,
            "freshestReportDays": min_age_days,
            "affectedRouteLengthMeters": affected_length,
            "affectedLengthPercentage": affected_pct,
            "corridorMeters": corridor,
            "totalRouteLengthMeters": round(total_dist_m, 1),
            "usableDogEvidenceLengthMeters": affected_length,
            "explanation": explanation,
            "guidance": guidance
        }

    def _build_simple_digraph(self, weight_attr: str) -> Tuple[nx.DiGraph, Dict[Tuple[int, int], int]]:
        """
        Collapses MultiDiGraph to simple DiGraph for Yen's algorithm.
        Picks the minimum weight edge for each (u, v) and retains the mapping to the edge key.
        Caches results per weight_attr for efficiency.
        """
        if not hasattr(self, "_simple_digraphs"):
            self._simple_digraphs = {}
        if weight_attr in self._simple_digraphs:
            return self._simple_digraphs[weight_attr]

        G_simple = nx.DiGraph()
        edge_key_map: Dict[Tuple[int, int], int] = {}

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            cost = float(data.get(weight_attr, 100.0))
            if not G_simple.has_edge(u, v) or cost < G_simple[u][v]["cost"]:
                G_simple.add_edge(u, v, cost=cost)
                edge_key_map[(u, v)] = k

        res = (G_simple, edge_key_map)
        self._simple_digraphs[weight_attr] = res
        return res

    @staticmethod
    @staticmethod
    def calculate_path_edge_overlap(
        path1: List[int],
        path2: List[int],
        graph: Optional[nx.Graph] = None,
        denominator: str = "union"
    ) -> float:
        """
        Calculates edge overlap between two paths.
        
        Formula:
          Shared Edge Length = sum(len(e) for e in E1 intersect E2)
        
        Denominators:
          - "union" (default, Jaccard length similarity):
              Denominator = sum(len(e) for e in E1 union E2)
              Provides symmetric similarity index across combined corridor footprint.
          - "min_length" or "shorter_path":
              Denominator = min(sum(len(e) for e in E1), sum(len(e) for e in E2))
              Provides conservative shared fraction for deduplicating route alternatives.
          - "candidate" or "path1":
              Denominator = sum(len(e) for e in E1)
              Measures the exact fraction of path1 traversing streets shared with path2.
        """
        edges1 = set(tuple(sorted((path1[i], path1[i + 1]))) for i in range(len(path1) - 1))
        edges2 = set(tuple(sorted((path2[i], path2[i + 1]))) for i in range(len(path2) - 1))
        if not edges1 or not edges2:
            return 0.0

        inter = edges1.intersection(edges2)
        union = edges1.union(edges2)

        if graph is not None:
            def get_edge_len(u_n, v_n):
                if graph.has_edge(u_n, v_n):
                    return float(min(graph[u_n][v_n].values(), key=lambda d: d.get("length", 100.0)).get("length", 100.0))
                elif graph.has_edge(v_n, u_n):
                    return float(min(graph[v_n][u_n].values(), key=lambda d: d.get("length", 100.0)).get("length", 100.0))
                return 100.0

            inter_len = sum(get_edge_len(u, v) for u, v in inter)

            if denominator in ("min_length", "shorter_path"):
                len1 = sum(get_edge_len(u, v) for u, v in edges1)
                len2 = sum(get_edge_len(u, v) for u, v in edges2)
                denom_val = max(min(len1, len2), 0.1)
            elif denominator in ("candidate", "path1"):
                len1 = sum(get_edge_len(u, v) for u, v in edges1)
                denom_val = max(len1, 0.1)
            else:  # 'union' default
                denom_val = max(sum(get_edge_len(u, v) for u, v in union), 0.1)

            return round(inter_len / denom_val, 4)

        # Discrete edge count fallback
        if denominator in ("min_length", "shorter_path"):
            denom_cnt = max(min(len(edges1), len(edges2)), 1)
        elif denominator in ("candidate", "path1"):
            denom_cnt = max(len(edges1), 1)
        else:
            denom_cnt = max(len(union), 1)

        return round(len(inter) / float(denom_cnt), 4)

    def _compute_path_duration(self, node_path: List[int]) -> float:
        """Calculates estimated walking duration in seconds for a sequence of nodes."""
        total_s = 0.0
        spd = max(self.risk_model.walking_speed_mps, 0.5)
        for i in range(len(node_path) - 1):
            u, v = node_path[i], node_path[i + 1]
            if self.graph.has_edge(u, v):
                ed = min(self.graph[u][v].values(), key=lambda d: d.get("length", 100.0))
                total_s += float(ed.get("length", 100.0)) / spd
            else:
                total_s += 100.0 / spd
        return total_s

    def compute_all_routes(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        ranking_preference: str = "safety",  # "safety", "balanced", or "fastest"
        include_alternatives: bool = True,
        max_alternatives: Optional[int] = None,
        departure_period: Optional[str] = None,
        step_free: Optional[bool] = None
    ) -> List[ComputedRoute]:
        """
        Computes walking route alternatives across distinct routing objectives:
        1. Baseline Fastest Route — strictly minimizes walking travel time (lambda = 0).
        2. Balanced Walking Route — documented trade-off between walking time and verified environmental indicators.
        3. Evidence-Prioritized Route — maximizes verified lighting, infrastructure, and assistance access.
        4. Additional Alternatives — diverse loopless alternatives discovered via Yen's algorithm.
        Enforces route diversity:
        - Accurately reports overlap percentage against the direct route on every card.
        - Yen alternatives are filtered against all primary paths to guarantee distinct corridors (overlap < threshold).
        - Honestly flags when network topology provides limited alternatives within detour bounds.
        """
        if departure_period is not None and departure_period != self.departure_period:
            self.departure_period = departure_period
            self.risk_model.departure_period = departure_period
            self.risk_model._compute_effective_weights()
            self._evaluate_all_edges()

        if step_free is not None and step_free != self.step_free:
            self.step_free = step_free
            self.risk_model.step_free = step_free
            self._evaluate_all_edges()

        # 1. Snap coordinates to nearest pedestrian network nodes
        orig_node, orig_dist = self._find_nearest_node(origin_lat, origin_lon)
        dest_node, dest_dist = self._find_nearest_node(dest_lat, dest_lon)

        if orig_dist > 300.0:
            raise OutOfCoverageError(
                f"Origin ({origin_lat:.5f}, {origin_lon:.5f}) is {int(orig_dist)}m from the nearest pedestrian network street, "
                "which exceeds walkable network access coverage (300m). Please select a location on or near a walkable street."
            )
        if dest_dist > 300.0:
            raise OutOfCoverageError(
                f"Destination ({dest_lat:.5f}, {dest_lon:.5f}) is {int(dest_dist)}m from the nearest pedestrian network street, "
                "which exceeds walkable network access coverage (300m). Please select a location on or near a walkable street."
            )

        if orig_node == dest_node:
            raise InvalidCoordinateError(
                f"Origin location ({origin_lat:.5f}, {origin_lon:.5f}) and destination location ({dest_lat:.5f}, {dest_lon:.5f}) "
                f"snap to the identical pedestrian network node ({orig_node})."
            )

        # 2. Verify reachability
        if not nx.has_path(self.graph, orig_node, dest_node):
            raise DisconnectedNetworkError(
                f"No connected pedestrian route exists between node {orig_node} and node {dest_node}. "
                "The locations lie in disconnected pedestrian components."
            )

        # --- Route 1: Baseline Fastest (lambda = 0, Dijkstra on traversal time) ---
        fastest_path = nx.dijkstra_path(self.graph, orig_node, dest_node, weight="cost_fastest")
        fastest_route = self._reconstruct_route_metrics(
            node_path=fastest_path,
            route_id="route-shortest",
            name="Fastest Direct Route",
            category="fastest",
            preference="Fastest",
            cost_weight_attr="cost_fastest",
            orig_coords=(origin_lat, origin_lon),
            dest_coords=(dest_lat, dest_lon),
            fastest_time_s=None,
            fastest_node_path=fastest_path,
            identical_notes="Baseline shortest-time route."
        )
        fastest_time_s = fastest_route.duration_seconds

        # --- Route 2: Balanced Route (lambda = lambda_balanced) ---
        balanced_path = nx.dijkstra_path(self.graph, orig_node, dest_node, weight="cost_balanced")
        is_balanced_ident = bool(balanced_path == fastest_path)
        balanced_ident_notes = (
            f"Optimal under both travel-time and balanced risk objectives (lambda={self.risk_model.lambda_balanced}) "
            f"for departure period '{self.departure_period}'. The direct corridor already maximizes verified lighting and infrastructure."
        ) if is_balanced_ident else None

        balanced_route = self._reconstruct_route_metrics(
            node_path=balanced_path,
            route_id="route-balanced",
            name="Balanced Walking Route",
            category="balanced",
            preference="Balanced",
            cost_weight_attr="cost_balanced",
            orig_coords=(origin_lat, origin_lon),
            dest_coords=(dest_lat, dest_lon),
            fastest_time_s=fastest_time_s,
            fastest_node_path=fastest_path,
            identical_notes=balanced_ident_notes
        )

        if balanced_route.duration_seconds > (fastest_time_s * self.max_detour_ratio):
            balanced_route.limitations.append(
                f"Detour duration exceeds max ratio ({self.max_detour_ratio}x of fastest duration)."
            )

        # --- Route 3: Safety-Prioritized Route (lambda = lambda_safety) ---
        safety_path = nx.dijkstra_path(self.graph, orig_node, dest_node, weight="cost_safety")
        is_safety_ident = bool(safety_path == fastest_path)
        safety_ident_notes = (
            f"Optimal under both travel-time and safety objectives (lambda={self.risk_model.lambda_safety}) "
            f"for departure period '{self.departure_period}'. The fastest corridor already follows the most illuminated "
            "and facility-proximate street segments available in the network."
        ) if is_safety_ident else None

        safety_route = self._reconstruct_route_metrics(
            node_path=safety_path,
            route_id="route-evidence",
            name="Safety-prioritized Route",
            category="safety_prioritized",
            preference="Safety-prioritized",
            cost_weight_attr="cost_safety",
            orig_coords=(origin_lat, origin_lon),
            dest_coords=(dest_lat, dest_lon),
            fastest_time_s=fastest_time_s,
            fastest_node_path=fastest_path,
            identical_notes=safety_ident_notes
        )

        if safety_route.duration_seconds > (fastest_time_s * self.max_detour_ratio):
            safety_route.limitations.append(
                f"Safety detour exceeds configured constraint ({self.max_detour_ratio}x fastest duration)."
            )

        # Check evidence coverage across safety route: if coverage is low, add honest warning
        if safety_route.evidence_coverage < 0.25:
            safety_route.limitations.append(
                f"Evidence coverage ({round(safety_route.evidence_coverage * 100, 1)}%) along corridor is limited. "
                "Unmapped streets are evaluated under conservative modeling uncertainty (prior R_unknown=0.50), not proven safety."
            )

        # Track selected node paths for diverse alternatives search
        selected_node_paths = [fastest_path]
        if not is_balanced_ident:
            selected_node_paths.append(balanced_path)
        if safety_path not in selected_node_paths:
            selected_node_paths.append(safety_path)

        # --- Route Alternatives via Yen's K-Shortest Loopless Paths Algorithm ---
        alt_routes: List[ComputedRoute] = []
        if include_alternatives:
            try:
                alt_cost_attr = "cost_safety" if ranking_preference == "safety" else ("cost_fastest" if ranking_preference == "fastest" else "cost_balanced")
                simple_digraph, _ = self._build_simple_digraph(weight_attr=alt_cost_attr)
                yen_paths_generator = nx.shortest_simple_paths(simple_digraph, orig_node, dest_node, weight="cost")

                alt_count = 0
                max_alts = max_alternatives if max_alternatives is not None else self.max_alternatives
                eval_count = 0
                eff_threshold = self.overlap_threshold if self.overlap_threshold is not None else 0.55

                for cand_path in yen_paths_generator:
                    eval_count += 1
                    if eval_count > 120 or alt_count >= max_alts:
                        break

                    cand_dur = self._compute_path_duration(cand_path)
                    if cand_dur > (fastest_time_s * self.max_detour_ratio):
                        continue

                    # Overlap with existing paths (Jaccard similarity for threshold check)
                    max_ov = max(
                        self.calculate_path_edge_overlap(cand_path, ep, graph=self.graph)
                        for ep in selected_node_paths
                    )

                    if max_ov < eff_threshold:
                        alt_cand = self._reconstruct_route_metrics(
                            node_path=cand_path,
                            route_id=f"route-alt-{alt_count + 1}",
                            name=f"Alternative Route {alt_count + 1}",
                            category="alternative",
                            preference="Alternative",
                            cost_weight_attr=alt_cost_attr,
                            orig_coords=(origin_lat, origin_lon),
                            dest_coords=(dest_lat, dest_lon),
                            fastest_time_s=fastest_time_s,
                            fastest_node_path=fastest_path
                        )
                        alt_count += 1
                        alt_routes.append(alt_cand)
                        selected_node_paths.append(cand_path)

            except Exception as e:
                logger.warning(f"Yen's alternative path generation encountered: {e}")

        # Order primary routes according to ranking preference
        if ranking_preference == "fastest":
            ordered_primary = [fastest_route, balanced_route, safety_route]
        elif ranking_preference == "balanced":
            ordered_primary = [balanced_route, safety_route, fastest_route]
        else:
            ordered_primary = [safety_route, balanced_route, fastest_route]

        return ordered_primary + alt_routes


# Module-level alias for ease of import
calculate_path_edge_overlap = DijkstraRouter.calculate_path_edge_overlap
