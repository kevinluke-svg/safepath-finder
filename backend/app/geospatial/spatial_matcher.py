"""
SafePath Finder — Geospatial Spatial Matcher Service
Uses Shapely STRtree spatial indexing to associate point observations
(crime incidents, community reports, lighting fixtures) with pedestrian street segments.
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

import networkx as nx
import osmnx as ox
import pyproj
from shapely.geometry import Point, LineString
from shapely.strtree import STRtree

from app.geospatial.exceptions import DataQualityError

logger = logging.getLogger(__name__)


@dataclass
class SpatialMatchResult:
    """Detailed result of matching a spatial point to a street network edge."""
    status: str  # "matched", "unmatched", "ambiguous"
    distance_meters: Optional[float]
    edge_u: Optional[int]
    edge_v: Optional[int]
    edge_key: Optional[int]
    match_method: str = "strtree_project"
    tolerance_meters: float = 30.0
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SpatialMatcher:
    """
    Associates point observations with pedestrian network edges using spatial indexing.
    Projects geometries to metric coordinate systems (UTM) to calculate true ground distances.
    Enforces configurable spatial tolerances to avoid false or overextended associations.
    """

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        default_tolerance_meters: float = 30.0,
        fallback_epsg: int = 32643
    ):
        self.default_tolerance_meters = default_tolerance_meters
        self.edges_list: List[Tuple[int, int, int, Dict[str, Any]]] = []
        self.geometries: List[LineString] = []
        self.tree: Optional[STRtree] = None
        self.transformer: Optional[pyproj.Transformer] = None
        self.projected_crs: str = f"EPSG:{fallback_epsg}"

        self._build_index(graph, fallback_epsg)

    def _build_index(self, graph: nx.MultiDiGraph, fallback_epsg: int) -> None:
        """Projects graph to metric UTM CRS and builds Shapely STRtree index."""
        if len(graph.edges) == 0:
            logger.warning("Graph contains 0 edges. SpatialMatcher initialized with empty index.")
            return

        try:
            # Attempt projection using OSMnx
            if "crs" not in graph.graph:
                graph.graph["crs"] = "EPSG:4326"
            projected_graph = ox.project_graph(graph)
            self.projected_crs = str(projected_graph.graph.get("crs", f"EPSG:{fallback_epsg}"))
        except Exception as e:
            logger.warning(f"Could not automatically project graph with OSMnx ({e}), using EPSG:{fallback_epsg}")
            projected_graph = graph
            self.projected_crs = f"EPSG:{fallback_epsg}"

        # Initialize Coordinate Transformer from WGS84 (EPSG:4326) to projected metric CRS
        try:
            self.transformer = pyproj.Transformer.from_crs(
                "EPSG:4326",
                self.projected_crs,
                always_xy=True
            )
        except Exception as e:
            logger.error(f"Failed to initialize pyproj transformer to {self.projected_crs}: {e}")
            self.transformer = None

        # Build list of metric LineStrings and associated edge references
        for u, v, k, data in projected_graph.edges(keys=True, data=True):
            geom = data.get("geometry")
            if geom is None:
                # Synthesize LineString from node coordinates if edge geometry not explicitly stored
                u_node = projected_graph.nodes[u]
                v_node = projected_graph.nodes[v]
                u_x, u_y = u_node.get("x", 0.0), u_node.get("y", 0.0)
                v_x, v_y = v_node.get("x", 0.0), v_node.get("y", 0.0)
                geom = LineString([(u_x, u_y), (v_x, v_y)])

            self.edges_list.append((u, v, k, data))
            self.geometries.append(geom)

        if self.geometries:
            self.tree = STRtree(self.geometries)
            logger.info(
                f"SpatialMatcher index built with {len(self.geometries)} edges. "
                f"Projected CRS: {self.projected_crs}"
            )

    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> None:
        """Validates geographic coordinates for numeric range and validity."""
        if not (isinstance(latitude, (int, float)) and isinstance(longitude, (int, float))):
            raise DataQualityError(f"Coordinates must be numeric, got lat={latitude}, lon={longitude}")
        if math.isnan(latitude) or math.isnan(longitude) or math.isinf(latitude) or math.isinf(longitude):
            raise DataQualityError(f"Invalid non-finite coordinates: lat={latitude}, lon={longitude}")
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            raise DataQualityError(f"Coordinates out of bounds: lat={latitude}, lon={longitude}")

    def match_point(
        self,
        latitude: float,
        longitude: float,
        tolerance_meters: Optional[float] = None
    ) -> SpatialMatchResult:
        """
        Projects a coordinate point and snaps to the nearest pedestrian street edge.
        Returns SpatialMatchResult with distance, edge IDs, and match status.
        """
        self.validate_coordinates(latitude, longitude)
        tolerance = tolerance_meters if tolerance_meters is not None else self.default_tolerance_meters

        if self.tree is None or not self.geometries or self.transformer is None:
            return SpatialMatchResult(
                status="unmatched",
                distance_meters=None,
                edge_u=None,
                edge_v=None,
                edge_key=None,
                tolerance_meters=tolerance,
                reason="Pedestrian network spatial index is unpopulated"
            )

        try:
            # Transform point from (lon, lat) WGS84 to metric projected coordinates
            px, py = self.transformer.transform(longitude, latitude)
            query_point = Point(px, py)

            # Query STRtree for the nearest edge LineString
            nearest_idx = self.tree.nearest(query_point)
            nearest_geom = self.geometries[nearest_idx]
            dist_meters = float(nearest_geom.distance(query_point))

            u, v, k, _ = self.edges_list[nearest_idx]

            if dist_meters <= tolerance:
                return SpatialMatchResult(
                    status="matched",
                    distance_meters=round(dist_meters, 2),
                    edge_u=u,
                    edge_v=v,
                    edge_key=k,
                    match_method="strtree_project",
                    tolerance_meters=tolerance,
                    reason=f"Matched to edge ({u}, {v}) within {round(dist_meters, 2)}m tolerance"
                )
            else:
                return SpatialMatchResult(
                    status="unmatched",
                    distance_meters=round(dist_meters, 2),
                    edge_u=None,
                    edge_v=None,
                    edge_key=None,
                    match_method="strtree_project",
                    tolerance_meters=tolerance,
                    reason=(
                        f"Nearest pedestrian segment ({u}, {v}) is {round(dist_meters, 1)}m away, "
                        f"which exceeds the configured tolerance of {tolerance}m."
                    )
                )
        except Exception as e:
            logger.error(f"Error during spatial match for ({latitude}, {longitude}): {e}")
            return SpatialMatchResult(
                status="unmatched",
                distance_meters=None,
                edge_u=None,
                edge_v=None,
                edge_key=None,
                tolerance_meters=tolerance,
                reason=f"Spatial matching exception: {str(e)}"
            )

    def batch_match(
        self,
        points: List[Tuple[str, float, float]],
        tolerance_meters: Optional[float] = None
    ) -> Dict[str, SpatialMatchResult]:
        """
        Batch-matches a list of (point_id, latitude, longitude) tuples.
        Returns a mapping of point_id -> SpatialMatchResult.
        """
        results: Dict[str, SpatialMatchResult] = {}
        for pid, lat, lon in points:
            try:
                results[pid] = self.match_point(lat, lon, tolerance_meters)
            except DataQualityError as e:
                results[pid] = SpatialMatchResult(
                    status="unmatched",
                    distance_meters=None,
                    edge_u=None,
                    edge_v=None,
                    edge_key=None,
                    tolerance_meters=tolerance_meters or self.default_tolerance_meters,
                    reason=f"Coordinate validation failure: {str(e)}"
                )
        return results
