"""
SafePath Finder — Pedestrian Facility Router (Police & Healthcare Assistance Access)
Calculates real walking distance and estimated walking time on the pedestrian network graph.
Maintains clear distinction between pedestrian-network routing and Euclidean straight-line distance.
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

import networkx as nx
import osmnx as ox

from app.geospatial.facilities_adapter import FacilityPoint

logger = logging.getLogger(__name__)

# Nominal pedestrian walking speed: 1.2 meters per second = 72 meters per minute
NOMINAL_WALKING_SPEED_MPS = 1.2
NOMINAL_WALKING_SPEED_MPM = NOMINAL_WALKING_SPEED_MPS * 60.0  # 72.0 m/min


@dataclass
class FacilityProximity:
    """Calculated walking access to a civic safety facility."""
    facility_type: str  # "police" or "hospital"
    nearest_facility_id: Optional[str]
    nearest_facility_name: Optional[str]
    distance_meters: float
    walking_time_minutes: float
    distance_type: str  # "network_walking" or "euclidean_straight_line"
    is_straight_line: bool
    caveat: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FacilityRouter:
    """
    Computes true pedestrian network walking distances and estimated walking times
    from pedestrian network nodes and street segments to the nearest police stations and hospitals.
    Enforces honest labeling: never substitutes straight-line distance without explicit marking.
    """

    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph
        self._undirected_graph: Optional[nx.Graph] = None

    def _get_routing_graph(self) -> nx.Graph:
        """Returns an undirected representation of the graph for bidirectional pedestrian walking."""
        if self._undirected_graph is None:
            # Pedestrians can generally walk bidirectionally along sidewalks/footways
            self._undirected_graph = self.graph.to_undirected(as_view=True)
        return self._undirected_graph

    @staticmethod
    def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes great-circle distance between two coordinate pairs in meters."""
        r = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c

    def snap_facilities_to_network(
        self,
        facilities: List[FacilityPoint]
    ) -> List[Tuple[FacilityPoint, int, float]]:
        """
        Maps each facility point to the nearest node in the pedestrian graph.
        Returns list of (FacilityPoint, nearest_node_id, snap_distance_meters).
        """
        snapped = []
        if len(self.graph.nodes) == 0:
            return snapped

        for fac in facilities:
            try:
                # Find nearest node by minimum haversine distance
                best_node = None
                best_dist = float("inf")
                for node_id, data in self.graph.nodes(data=True):
                    n_lat = data.get("y", 0.0)
                    n_lon = data.get("x", 0.0)
                    d = self.haversine_distance_meters(fac.latitude, fac.longitude, n_lat, n_lon)
                    if d < best_dist:
                        best_dist = d
                        best_node = node_id

                if best_node is not None:
                    snapped.append((fac, int(best_node), float(best_dist)))
            except Exception as e:
                logger.warning(f"Could not snap facility {fac.id} ({fac.name}) to network: {e}")
        return snapped

    def compute_facility_distances_for_nodes(
        self,
        facilities: List[FacilityPoint],
        facility_type: str
    ) -> Dict[int, FacilityProximity]:
        """
        Calculates shortest walking distance on the pedestrian graph from every node
        to the nearest facility of the given type (e.g. 'police' or 'hospital').
        """
        results: Dict[int, FacilityProximity] = {}
        filtered_facilities = [f for f in facilities if f.facility_type == facility_type]

        if not filtered_facilities or len(self.graph.nodes) == 0:
            logger.info(f"No facilities of type '{facility_type}' available for network calculation.")
            return results

        snapped = self.snap_facilities_to_network(filtered_facilities)
        if not snapped:
            return results

        routing_graph = self._get_routing_graph()

        # Map each facility node to the best facility record
        node_to_facility: Dict[int, Tuple[FacilityPoint, float]] = {}
        facility_nodes: List[int] = []
        for fac, node_id, snap_dist in snapped:
            facility_nodes.append(node_id)
            if node_id not in node_to_facility or snap_dist < node_to_facility[node_id][1]:
                node_to_facility[node_id] = (fac, snap_dist)

        # Multi-source Dijkstra: shortest path from any facility node to all reachable nodes
        try:
            shortest_lengths = nx.multi_source_dijkstra_path_length(
                routing_graph,
                sources=facility_nodes,
                weight="length"
            )
        except Exception as e:
            logger.error(f"Multi-source Dijkstra failed for {facility_type}: {e}")
            shortest_lengths = {}

        # Build proximity results for every node in the graph
        for node_id, data in self.graph.nodes(data=True):
            node_lat = data.get("y", 0.0)
            node_lon = data.get("x", 0.0)

            if node_id in shortest_lengths:
                net_dist = float(shortest_lengths[node_id])
                walk_mins = round(net_dist / NOMINAL_WALKING_SPEED_MPM, 1)

                # Identify closest facility
                closest_fac = filtered_facilities[0]
                min_straight = float("inf")
                for fac in filtered_facilities:
                    st_dist = self.haversine_distance_meters(node_lat, node_lon, fac.latitude, fac.longitude)
                    if st_dist < min_straight:
                        min_straight = st_dist
                        closest_fac = fac

                results[node_id] = FacilityProximity(
                    facility_type=facility_type,
                    nearest_facility_id=closest_fac.id,
                    nearest_facility_name=closest_fac.name,
                    distance_meters=round(net_dist, 1),
                    walking_time_minutes=walk_mins,
                    distance_type="network_walking",
                    is_straight_line=False,
                    caveat=(
                        f"Pedestrian network walking distance (assumed walking speed {NOMINAL_WALKING_SPEED_MPS} m/s). "
                        "Proximity to assistance does not imply zero crime risk or verified availability."
                    )
                )
            else:
                # Disconnected component: compute straight-line distance with explicit caveat
                closest_fac = filtered_facilities[0]
                min_dist = float("inf")
                for fac in filtered_facilities:
                    d = self.haversine_distance_meters(node_lat, node_lon, fac.latitude, fac.longitude)
                    if d < min_dist:
                        min_dist = d
                        closest_fac = fac

                walk_mins = round(min_dist / NOMINAL_WALKING_SPEED_MPM, 1)
                results[node_id] = FacilityProximity(
                    facility_type=facility_type,
                    nearest_facility_id=closest_fac.id,
                    nearest_facility_name=closest_fac.name,
                    distance_meters=round(min_dist, 1),
                    walking_time_minutes=walk_mins,
                    distance_type="euclidean_straight_line",
                    is_straight_line=True,
                    caveat=(
                        "DISCONNECTED SUBGRAPH: Distance is straight-line Euclidean distance, "
                        "NOT verified walking distance. Does not account for pedestrian barriers, fences, or detours."
                    )
                )

        return results

    def get_edge_facility_proximity(
        self,
        edge_u: int,
        edge_v: int,
        police_node_prox: Dict[int, FacilityProximity],
        hospital_node_prox: Dict[int, FacilityProximity]
    ) -> Dict[str, Optional[FacilityProximity]]:
        """
        Calculates facility proximity for an edge as the minimum distance of its endpoints.
        """
        police_prox = None
        u_pol = police_node_prox.get(edge_u)
        v_pol = police_node_prox.get(edge_v)
        if u_pol and v_pol:
            police_prox = u_pol if u_pol.distance_meters <= v_pol.distance_meters else v_pol
        elif u_pol:
            police_prox = u_pol
        elif v_pol:
            police_prox = v_pol

        hosp_prox = None
        u_hosp = hospital_node_prox.get(edge_u)
        v_hosp = hospital_node_prox.get(edge_v)
        if u_hosp and v_hosp:
            hosp_prox = u_hosp if u_hosp.distance_meters <= v_hosp.distance_meters else v_hosp
        elif u_hosp:
            hosp_prox = u_hosp
        elif v_hosp:
            hosp_prox = v_hosp

        return {
            "police": police_prox,
            "hospital": hosp_prox
        }
