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
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString

from app.core.config import settings
from app.geospatial.exceptions import (
    DisconnectedNetworkError,
    InvalidCoordinateError,
    OutOfCoverageError,
)
from app.geospatial.segment_risk import SegmentRiskModel, SegmentRiskProfile

logger = logging.getLogger(__name__)


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DijkstraRouter:
    """
    Pedestrian routing engine providing:
    - Baseline fastest path (Dijkstra on travel time T_e)
    - Multi-criteria risk-weighted paths (Balanced & Safety-prioritized)
    - Yen's K-shortest loopless alternative paths
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
        max_alternatives: Optional[int] = None
    ):
        self.graph = graph
        self.risk_model = risk_model or SegmentRiskModel()
        self.max_detour_ratio = max_detour_ratio or settings.ROUTING_MAX_DETOUR_RATIO
        self.overlap_threshold = overlap_threshold or settings.ROUTING_ALTERNATIVE_OVERLAP_THRESHOLD
        self.max_alternatives = max_alternatives or settings.ROUTING_MAX_ALTERNATIVES

        if facilities_result:
            self._attach_facilities(facilities_result)
        if crime_dataset:
            self._attach_crime(crime_dataset)
        if community_reports:
            self._attach_community_reports(community_reports)

        self.edge_profiles: Dict[Tuple[int, int, int], SegmentRiskProfile] = {}
        self._prepare_graph_edge_costs()

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

            for rep in community_reports:
                lat = getattr(rep, "latitude", None)
                lon = getattr(rep, "longitude", None)
                if lat is not None and lon is not None:
                    node_id, dist = self._find_nearest_node(lat, lon)
                    if dist <= 300.0:
                        for neighbor in self.graph.successors(node_id):
                            for k in self.graph[node_id][neighbor]:
                                self.graph[node_id][neighbor][k]["community_reports_count"] += 1
        except Exception as e:
            logger.warning(f"Could not attach community reports to graph: {e}")

    def _prepare_graph_edge_costs(self) -> None:
        """
        Evaluates risk profiles and attaches non-negative, finite Dijkstra traversal
        costs (cost_fastest, cost_balanced, cost_safety) to all graph edges.
        """
        for u, v, k, data in self.graph.edges(keys=True, data=True):
            length_m = float(data.get("length", 100.0))
            lit_tag = data.get("lit")
            if isinstance(lit_tag, list):
                lit_tag = lit_tag[0] if lit_tag else None

            # Check if edge has attached assistance or crime data
            pol_dist = data.get("nearest_police_distance_meters")
            pol_time = (pol_dist / (settings.WALKING_SPEED_MPS * 60.0)) if pol_dist else None
            hosp_dist = data.get("nearest_hospital_distance_meters")
            hosp_time = (hosp_dist / (settings.WALKING_SPEED_MPS * 60.0)) if hosp_dist else None

            crime_cnt = int(data.get("crime_count", 0))
            crime_rate = float(data.get("crime_rate_per_km", 0.0))
            comm_cnt = int(data.get("community_reports_count", 0))
            has_crime = bool(data.get("has_crime_dataset", False) or crime_cnt > 0)

            profile = self.risk_model.evaluate_edge(
                edge_data=data,
                edge_length_meters=length_m,
                lit_status=lit_tag or "unmapped",
                police_walking_minutes=pol_time,
                hospital_walking_minutes=hosp_time,
                crime_count=crime_cnt,
                crime_rate_per_km=crime_rate,
                community_reports_count=comm_cnt,
                has_crime_dataset=has_crime
            )

            self.edge_profiles[(u, v, k)] = profile

            # Ensure non-negative, finite costs on graph edges
            data["cost_fastest"] = max(profile.cost_fastest, 0.01)
            data["cost_balanced"] = max(profile.cost_balanced, 0.01)
            data["cost_safety"] = max(profile.cost_safety, 0.01)
            data["length"] = length_m

    def _find_nearest_node(self, lat: float, lon: float) -> Tuple[int, float]:
        """Snaps coordinate pair to nearest graph node using minimum haversine distance."""
        best_node = None
        min_dist = float("inf")
        r = 6371000.0  # meters

        phi1 = math.radians(lat)
        for nid, data in self.graph.nodes(data=True):
            n_lat = data.get("y", 0.0)
            n_lon = data.get("x", 0.0)
            phi2 = math.radians(n_lat)
            dphi = math.radians(n_lat - lat)
            dlam = math.radians(n_lon - lon)

            a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
            d = r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
            if d < min_dist:
                min_dist = d
                best_node = nid

        if best_node is None:
            raise DisconnectedNetworkError("Pedestrian network graph contains 0 nodes.")
        return int(best_node), float(min_dist)

    def _get_best_edge_key(self, u: int, v: int, weight_attr: str) -> int:
        """Finds edge key with lowest weight for parallel edges between u and v."""
        edges = self.graph[u][v]
        best_k = min(edges.keys(), key=lambda k: edges[k].get(weight_attr, float("inf")))
        return best_k

    def _reconstruct_route_metrics(
        self,
        node_path: List[int],
        route_id: str,
        name: str,
        category: str,
        preference: str,
        cost_weight_attr: str,
        orig_coords: Optional[Tuple[float, float]] = None,
        dest_coords: Optional[Tuple[float, float]] = None
    ) -> ComputedRoute:
        """
        Reconstructs full metric geometry, total distance, duration, risk, coverage,
        and human-readable explanations for a given node sequence.
        """
        total_dist_m = 0.0
        total_time_s = 0.0
        total_cost = 0.0
        time_weighted_risk_sum = 0.0
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
                "evidenceCoverage": cov_q,
                "litStatus": lit_st,
                "geometry": pts
            })

        # Connect exact origin coordinates if offset from snapped first node (doorstep access up to 120m)
        if orig_coords is not None and geometry_coords:
            first_pt = geometry_coords[0]
            offset_deg = math.hypot(orig_coords[0] - first_pt[0], orig_coords[1] - first_pt[1])
            if 0.00005 < offset_deg <= 0.0012:
                geometry_coords.insert(0, [round(orig_coords[0], 6), round(orig_coords[1], 6)])

        # Connect exact destination coordinates if offset from snapped last node (doorstep access up to 120m)
        if dest_coords is not None and geometry_coords:
            last_pt = geometry_coords[-1]
            offset_deg = math.hypot(dest_coords[0] - last_pt[0], dest_coords[1] - last_pt[1])
            if 0.00005 < offset_deg <= 0.0012:
                geometry_coords.append([round(dest_coords[0], 6), round(dest_coords[1], 6)])

        # Calculate time-weighted averages
        mean_route_risk = round(time_weighted_risk_sum / max(total_time_s, 0.1), 4)
        mean_evidence_cov = round(time_weighted_cov_sum / max(total_time_s, 0.1), 4)
        has_insufficient = (mean_evidence_cov < self.risk_model.min_coverage_threshold)

        lit_pct = round((lit_len / max(total_dist_m, 1.0)) * 100.0, 1)
        unlit_pct = round((unlit_len / max(total_dist_m, 1.0)) * 100.0, 1)
        unmapped_pct = round((unmapped_len / max(total_dist_m, 1.0)) * 100.0, 1)
        conf_pct = round((conflicting_len / max(total_dist_m, 1.0)) * 100.0, 1)

        duration_mins = round(total_time_s / 60.0, 1)

        # Build characteristics and trade-offs
        characteristics = [
            f"{lit_pct}% verified street lighting",
            f"Walking distance {int(total_dist_m)}m (~{duration_mins} min)",
        ]
        if min_pol_dist < float("inf"):
            characteristics.append(f"Nearest police facility within {int(min_pol_dist)}m")
        if crime_total > 0:
            characteristics.append(f"{crime_total} historical crime record(s) along segments")
        if unmapped_pct > 40.0:
            characteristics.append(f"{unmapped_pct}% unmapped lighting (uncertainty preserved)")

        if category == "fastest":
            ranking_exp = (
                "Fastest route minimizing pedestrian traversal time (lambda=0). "
                "May traverse unlit, narrow, or unmapped streets to reduce travel time."
            )
            tradeoffs = "Baseline shortest duration. Does not divert to avoid darker or lower-evidence segments."
        elif category == "balanced":
            ranking_exp = (
                f"Balanced route penalizing risk with moderate weight (lambda={self.risk_model.lambda_balanced}). "
                "Balances walking duration with verified lighting and assistance accessibility."
            )
            tradeoffs = "Slightly longer than fastest path to prefer corridors with documented lighting."
        elif category == "safety_prioritized":
            ranking_exp = (
                f"Safety-prioritized route with high risk penalty (lambda={self.risk_model.lambda_safety}). "
                "Strongly avoids unlit, conflicting, and higher-crime segments."
            )
            tradeoffs = (
                f"Route risk indicator reduced to {mean_route_risk} (from {lit_pct}% lit streets), "
                "at the expense of additional walking distance."
            )
        else:
            ranking_exp = "Distinct topological alternative route generated via Yen's loopless paths algorithm."
            tradeoffs = "Alternative street sequence providing pedestrian route diversity."

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
                f"Lit streets: {lit_pct}%"
            ],
            source_metadata={
                "network": "OpenStreetMap pedestrian graph",
                "licensing": "ODbL 1.0",
                "algorithm": "Dijkstra / Yen loopless paths"
            },
            node_path=node_path,
            geometry=geometry_coords,
            segments=segments_output,
            limitations=sorted(list(route_limitations))
        )

    def _build_simple_digraph(self, weight_attr: str) -> Tuple[nx.DiGraph, Dict[Tuple[int, int], int]]:
        """
        Collapses MultiDiGraph to simple DiGraph for Yen's algorithm.
        Picks the minimum weight edge for each (u, v) and retains the mapping to the edge key.
        """
        G_simple = nx.DiGraph()
        edge_key_map: Dict[Tuple[int, int], int] = {}

        for u, v, k, data in self.graph.edges(keys=True, data=True):
            cost = float(data.get(weight_attr, 100.0))
            if not G_simple.has_edge(u, v) or cost < G_simple[u][v]["cost"]:
                G_simple.add_edge(u, v, cost=cost)
                edge_key_map[(u, v)] = k

        return G_simple, edge_key_map

    @staticmethod
    def calculate_path_edge_overlap(path1: List[int], path2: List[int]) -> float:
        """
        Calculates Jaccard similarity of edges between two paths.
        Overlap = |E1 intersect E2| / |E1 union E2|
        """
        edges1 = set((path1[i], path1[i + 1]) for i in range(len(path1) - 1))
        edges2 = set((path2[i], path2[i + 1]) for i in range(len(path2) - 1))
        if not edges1 or not edges2:
            return 0.0
        intersection = len(edges1.intersection(edges2))
        union = len(edges1.union(edges2))
        return intersection / float(union) if union > 0 else 0.0

    def compute_all_routes(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        walking_speed_mps: Optional[float] = None,
        ranking_preference: str = "safety",
        include_alternatives: bool = True,
        max_alternatives: Optional[int] = None
    ) -> List[ComputedRoute]:
        """
        Computes the three primary routes (Fastest, Balanced, Safety-prioritized) via separate
        Dijkstra runs, plus additional distinct loopless alternatives via Yen's algorithm.
        """
        if walking_speed_mps and walking_speed_mps > 0:
            self.risk_model.walking_speed_mps = walking_speed_mps
            self._prepare_graph_edge_costs()

        # 1. Snap origin and destination coordinates to network
        orig_node, orig_snap_dist = self._find_nearest_node(origin_lat, origin_lon)
        dest_node, dest_snap_dist = self._find_nearest_node(dest_lat, dest_lon)

        if orig_snap_dist > 500.0:
            raise OutOfCoverageError(
                f"Origin ({origin_lat:.5f}, {origin_lon:.5f}) is {int(orig_snap_dist)}m from the nearest pedestrian network street, "
                "which exceeds walkable network access coverage (500m). Please select a location on or near a walkable street."
            )
        if dest_snap_dist > 500.0:
            raise OutOfCoverageError(
                f"Destination ({dest_lat:.5f}, {dest_lon:.5f}) is {int(dest_snap_dist)}m from the nearest pedestrian network street, "
                "which exceeds walkable network access coverage (500m). Please select a location on or near a walkable street."
            )

        if orig_node == dest_node:
            raise InvalidCoordinateError(
                f"Origin ({origin_lat}, {origin_lon}) and destination ({dest_lat}, {dest_lon}) "
                f"snap to the identical pedestrian network node ({orig_node})."
            )

        # 2. Verify reachability
        if not nx.has_path(self.graph, orig_node, dest_node):
            raise DisconnectedNetworkError(
                f"No connected pedestrian route exists between node {orig_node} and node {dest_node}. "
                "The locations lie in disconnected pedestrian components."
            )

        selected_node_paths: List[List[int]] = []

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
            dest_coords=(dest_lat, dest_lon)
        )
        fastest_route.is_identical_to_fastest = True
        fastest_route.identical_notes = "Baseline shortest-time route."
        selected_node_paths.append(fastest_path)
        fastest_time_s = fastest_route.duration_seconds

        # --- Route 2: Balanced Route (lambda = lambda_balanced) ---
        balanced_path = nx.dijkstra_path(self.graph, orig_node, dest_node, weight="cost_balanced")
        balanced_route = self._reconstruct_route_metrics(
            node_path=balanced_path,
            route_id="route-balanced",
            name="Balanced Walking Route",
            category="balanced",
            preference="Balanced",
            cost_weight_attr="cost_balanced",
            orig_coords=(origin_lat, origin_lon),
            dest_coords=(dest_lat, dest_lon)
        )

        if balanced_path == fastest_path:
            balanced_route.is_identical_to_fastest = True
            balanced_route.identical_notes = "Balanced trade-off selects the same optimal path as the fastest route under current risk weights."

        # Detour constraint check
        if balanced_route.duration_seconds > (fastest_time_s * self.max_detour_ratio):
            balanced_route.limitations.append(
                f"Detour duration exceeds max ratio ({self.max_detour_ratio}x of fastest duration)."
            )
        selected_node_paths.append(balanced_path)

        # --- Route 3: Safety-Prioritized Route (lambda = lambda_safety) ---
        safety_path = nx.dijkstra_path(self.graph, orig_node, dest_node, weight="cost_safety")
        safety_route = self._reconstruct_route_metrics(
            node_path=safety_path,
            route_id="route-evidence",
            name="Safety-prioritized Route",
            category="safety_prioritized",
            preference="Safety-prioritized",
            cost_weight_attr="cost_safety",
            orig_coords=(origin_lat, origin_lon),
            dest_coords=(dest_lat, dest_lon)
        )

        # Compare trade-offs between fastest and safety-prioritized
        time_diff_min = round((safety_route.duration_seconds - fastest_time_s) / 60.0, 1)
        risk_diff = round(fastest_route.route_risk_indicator - safety_route.route_risk_indicator, 3)
        if time_diff_min > 0 and risk_diff > 0:
            safety_route.tradeoffs = (
                f"Adds ~{time_diff_min} min walking time compared to fastest route to reduce "
                f"effective risk indicator by {risk_diff} (prefers {safety_route.lit_percentage}% lit streets)."
            )
        elif time_diff_min == 0:
            safety_route.tradeoffs = (
                "Fastest route already follows the safest corridor; no additional walking detour needed."
            )

        if safety_route.duration_seconds > (fastest_time_s * self.max_detour_ratio):
            safety_route.limitations.append(
                f"Safety detour exceeds configured constraint ({self.max_detour_ratio}x fastest duration)."
            )
        if safety_path == fastest_path:
            safety_route.is_identical_to_fastest = True
            safety_route.identical_notes = "The fastest route already follows the safest corridor with highest verified lighting; no detour needed under the current safety model."
        elif safety_path == balanced_path:
            safety_route.identical_notes = "Safety-prioritized route selects the same path as the balanced route."

        selected_node_paths.append(safety_path)

        # --- Route Alternatives via Yen's K-Shortest Loopless Paths Algorithm ---
        alt_routes: List[ComputedRoute] = []
        if include_alternatives:
            try:
                simple_digraph, _ = self._build_simple_digraph(weight_attr="cost_balanced")
                yen_paths_generator = nx.shortest_simple_paths(simple_digraph, orig_node, dest_node, weight="cost")

                alt_count = 0
                max_alts = max_alternatives if max_alternatives is not None else self.max_alternatives
                for cand_path in yen_paths_generator:
                    # Check if path is duplicate or near-duplicate of existing selected paths
                    is_duplicate = False
                    for existing_path in selected_node_paths:
                        overlap = self.calculate_path_edge_overlap(cand_path, existing_path)
                        if overlap >= self.overlap_threshold:
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        alt_count += 1
                        alt_route = self._reconstruct_route_metrics(
                            node_path=cand_path,
                            route_id=f"route-alt-{alt_count}",
                            name=f"Alternative Route {alt_count}",
                            category="alternative",
                            preference="Alternative",
                            cost_weight_attr="cost_balanced",
                            orig_coords=(origin_lat, origin_lon),
                            dest_coords=(dest_lat, dest_lon)
                        )
                        alt_routes.append(alt_route)
                        selected_node_paths.append(cand_path)

                        if alt_count >= max_alts:
                            break
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
