"""
SafePath Finder — Pedestrian Street Network Adapter & Caching
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

import networkx as nx
import osmnx as ox

from app.core.config import settings
from app.geospatial.study_area import StudyArea
from app.geospatial.exceptions import (
    NetworkRetrievalError,
    DisconnectedNetworkError,
)

logger = logging.getLogger(__name__)

# Configure OSMnx settings for pedestrian safety analysis
ox.settings.http_user_agent = "SafePathFinder/1.0 (Research Pedestrian Safety Platform; contact@safepath.org)"
ox.settings.requests_timeout = 60
# Retain vital lighting and pedestrian attributes on ways
EXTRA_WAY_TAGS = ["lit", "foot", "sidewalk", "surface", "footway", "bicycle", "step_count", "incline"]
for tag in EXTRA_WAY_TAGS:
    if tag not in ox.settings.useful_tags_way:
        ox.settings.useful_tags_way.append(tag)


@dataclass
class NetworkResult:
    """Summary and graph payload from pedestrian network retrieval."""
    graph: nx.MultiDiGraph
    study_area_name: str
    nodes_count: int
    edges_count: int
    connected_components_count: int
    largest_component_nodes_count: int
    largest_component_ratio: float
    is_cached: bool
    cache_path: Optional[str]
    retrieved_at: str
    attribution: str = "© OpenStreetMap contributors, Open Database License (ODbL) 1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "studyAreaName": self.study_area_name,
            "nodesCount": self.nodes_count,
            "edgesCount": self.edges_count,
            "connectedComponentsCount": self.connected_components_count,
            "largestComponentNodesCount": self.largest_component_nodes_count,
            "largestComponentRatio": round(self.largest_component_ratio, 4),
            "isCached": self.is_cached,
            "cachePath": self.cache_path,
            "retrievedAt": self.retrieved_at,
            "attribution": self.attribution
        }


class BaseNetworkAdapter(ABC):
    """Abstract interface for street network retrieval to decouple routing from data sources."""

    @abstractmethod
    def get_pedestrian_network(self, study_area: StudyArea, force_reload: bool = False) -> NetworkResult:
        """Retrieves pedestrian network graph for the study area, with caching."""
        pass

    @abstractmethod
    def find_nearest_node(self, graph: nx.MultiDiGraph, lat: float, lon: float) -> Tuple[int, float]:
        """Finds nearest network node to given coordinates, returning (node_id, distance_meters)."""
        pass

    @abstractmethod
    def check_reachability(self, graph: nx.MultiDiGraph, origin_node: int, dest_node: int) -> bool:
        """Verifies topological reachability between two nodes."""
        pass


class OsmNetworkAdapter(BaseNetworkAdapter):
    """
    Concrete adapter retrieving pedestrian-accessible networks from OpenStreetMap
    via OSMnx, with filesystem caching in GraphML format.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or settings.GEOSPATIAL_CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_paths(self, study_area: StudyArea) -> Tuple[str, str]:
        graph_path = os.path.join(self.cache_dir, f"pedestrian_{study_area.slug}.graphml")
        meta_path = os.path.join(self.cache_dir, f"pedestrian_{study_area.slug}_meta.json")
        return graph_path, meta_path

    def get_pedestrian_network(self, study_area: StudyArea, force_reload: bool = False) -> NetworkResult:
        """
        Retrieves pedestrian-accessible network within study area bounding box.
        Reads from GraphML cache when available, or queries Overpass API.
        """
        graph_path, meta_path = self._get_cache_paths(study_area)

        # 1. Attempt Cache Load
        if not force_reload and os.path.isfile(graph_path):
            try:
                logger.info(f"Loading cached pedestrian network from {graph_path}")
                graph = ox.load_graphml(graph_path)
                meta = {}
                if os.path.isfile(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)

                nodes_count = len(graph.nodes)
                edges_count = len(graph.edges)
                comps = list(nx.weakly_connected_components(graph))
                comp_count = len(comps)
                largest_count = len(max(comps, key=len)) if comps else 0
                largest_ratio = (largest_count / nodes_count) if nodes_count > 0 else 0.0

                return NetworkResult(
                    graph=graph,
                    study_area_name=study_area.name,
                    nodes_count=nodes_count,
                    edges_count=edges_count,
                    connected_components_count=comp_count,
                    largest_component_nodes_count=largest_count,
                    largest_component_ratio=largest_ratio,
                    is_cached=True,
                    cache_path=graph_path,
                    retrieved_at=meta.get("retrievedAt", datetime.now(timezone.utc).isoformat()),
                    attribution="© OpenStreetMap contributors, Open Database License (ODbL) 1.0"
                )
            except Exception as e:
                logger.warning(f"Corrupted cache file {graph_path}, refetching: {e}")

        # 2. Live Overpass Retrieval
        logger.info(f"Downloading pedestrian network for '{study_area.name}' via OSMnx Overpass...")
        try:
            if study_area.place_name:
                graph = ox.graph_from_place(
                    study_area.place_name,
                    network_type="walk",
                    simplify=True,
                    retain_all=True
                )
            else:
                # OSMnx 2.x expects bbox as (left, bottom, right, top) = (west, south, east, north)
                graph = ox.graph_from_bbox(
                    bbox=study_area.bbox_osmnx,
                    network_type="walk",
                    simplify=True,
                    retain_all=True
                )
        except Exception as err:
            # If network request fails, check if we have a stale cache to fall back on
            if os.path.isfile(graph_path):
                logger.error(f"Live network download failed ({err}), using stale cache fallback.")
                graph = ox.load_graphml(graph_path)
                return NetworkResult(
                    graph=graph,
                    study_area_name=study_area.name,
                    nodes_count=len(graph.nodes),
                    edges_count=len(graph.edges),
                    connected_components_count=nx.number_weakly_connected_components(graph),
                    largest_component_nodes_count=len(max(nx.weakly_connected_components(graph), key=len)),
                    largest_component_ratio=1.0,
                    is_cached=True,
                    cache_path=graph_path,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    attribution="© OpenStreetMap contributors (Stale Cache Fallback)"
                )
            raise NetworkRetrievalError(
                f"Failed to retrieve pedestrian network from OpenStreetMap for '{study_area.name}': {str(err)}"
            ) from err

        nodes_count = len(graph.nodes)
        edges_count = len(graph.edges)
        if nodes_count == 0:
            raise NetworkRetrievalError(
                f"Retrieved 0 pedestrian nodes for study area '{study_area.name}' "
                f"[bbox: {study_area.bbox}]. Network coverage is missing."
            )

        # 3. Analyze Connectivity
        comps = list(nx.weakly_connected_components(graph))
        comp_count = len(comps)
        largest_count = len(max(comps, key=len)) if comps else 0
        largest_ratio = (largest_count / nodes_count) if nodes_count > 0 else 0.0

        # 4. Save to Cache
        try:
            ox.save_graphml(graph, graph_path)
            now_iso = datetime.now(timezone.utc).isoformat()
            meta_data = {
                "studyArea": study_area.to_dict(),
                "nodesCount": nodes_count,
                "edgesCount": edges_count,
                "connectedComponentsCount": comp_count,
                "largestComponentRatio": largest_ratio,
                "retrievedAt": now_iso,
                "attribution": "© OpenStreetMap contributors, Open Database License (ODbL) 1.0"
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)
            logger.info(f"Persisted pedestrian network to {graph_path}")
        except Exception as e:
            logger.error(f"Failed to cache pedestrian network to {graph_path}: {e}")

        return NetworkResult(
            graph=graph,
            study_area_name=study_area.name,
            nodes_count=nodes_count,
            edges_count=edges_count,
            connected_components_count=comp_count,
            largest_component_nodes_count=largest_count,
            largest_component_ratio=largest_ratio,
            is_cached=False,
            cache_path=graph_path,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            attribution="© OpenStreetMap contributors, Open Database License (ODbL) 1.0"
        )

    def find_nearest_node(self, graph: nx.MultiDiGraph, lat: float, lon: float) -> Tuple[int, float]:
        """
        Maps a coordinate to the nearest pedestrian network node.
        Returns (node_id, distance_meters).
        """
        node, dist = ox.distance.nearest_nodes(graph, X=lon, Y=lat, return_dist=True)
        return int(node), float(dist)

    def check_reachability(self, graph: nx.MultiDiGraph, origin_node: int, dest_node: int) -> bool:
        """
        Verifies topological connectivity between origin and destination nodes.
        Raises DisconnectedNetworkError if no path exists.
        """
        if not nx.has_path(graph, origin_node, dest_node):
            raise DisconnectedNetworkError(
                f"No connected pedestrian path exists between origin node {origin_node} and destination node {dest_node}. "
                "The locations fall into disconnected pedestrian subgraphs."
            )
        return True
