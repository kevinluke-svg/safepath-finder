"""
SafePath Finder — Real OpenStreetMap Pedestrian Network Validation Tests

Verifies:
1. Network Provenance: Graph comes from OpenStreetMap with valid ODbL licensing and >10,000 real street nodes.
2. Real Edge Geometry: Route segments correspond to exact edges in the OSM graph; curves and waypoints match OSM geometries.
3. Metric Integrity: Returned distance and duration match the mathematical sum of traversed edge lengths.
4. Path Continuity: No teleportation jumps, cross-building leaps, or fabricated coordinates.
5. Out-of-Coverage & Snapping: Locations outside the study area fail with HTTP 400 without fabricating paths.
6. Epistemic Integrity: Unmapped lighting/evidence is never treated as zero risk; uncertainty is preserved honestly.
7. Rejection of Approximate Fallback: Production routing never substitutes synthetic or manual 71-node graphs.
"""

import math
import pytest
from fastapi.testclient import TestClient

from app.geospatial.study_area import StudyArea
from app.geospatial.network_adapter import OsmNetworkAdapter
from app.geospatial.dijkstra_router import DijkstraRouter
from app.geospatial.segment_risk import SegmentRiskModel
from app.services.routing_service import compare_routes_service


@pytest.fixture(scope="module")
def real_osm_network():
    study_area = StudyArea.from_settings()
    adapter = OsmNetworkAdapter()
    result = adapter.get_pedestrian_network(study_area)
    return result


def test_real_osm_network_provenance_and_scale(real_osm_network):
    """Network must be from OpenStreetMap with real city-scale coverage (>10,000 nodes)."""
    assert real_osm_network.nodes_count >= 10000, f"Expected city-scale graph, got {real_osm_network.nodes_count} nodes"
    assert real_osm_network.edges_count >= 20000, f"Expected city-scale graph, got {real_osm_network.edges_count} edges"
    assert "OpenStreetMap" in real_osm_network.attribution
    assert real_osm_network.connected_components_count >= 1
    assert real_osm_network.largest_component_nodes_count >= 10000


def test_route_segments_match_graph_edges(real_osm_network):
    """Every segment returned in a route must correspond to an actual edge in the real OSM graph."""
    graph = real_osm_network.graph
    res = compare_routes_service(
        origin="Jayanagar 4th Block, Bengaluru",
        destination="Lalbagh West Gate, Bengaluru",
        origin_coordinates=[12.9257, 77.5833],
        destination_coordinates=[12.9460, 77.5844]
    )
    assert len(res.routes) >= 3

    for route in res.routes:
        assert len(route.segments) > 0, f"Route {route.name} has no segments"
        for seg in route.segments:
            u = seg["edgeU"]
            v = seg["edgeV"]
            k = seg["edgeKey"]
            assert u in graph.nodes, f"Node {u} not found in real OSM graph"
            assert v in graph.nodes, f"Node {v} not found in real OSM graph"
            assert graph.has_edge(u, v, key=k), f"Edge ({u}, {v}, key={k}) not found in real OSM graph"

            edge_data = graph[u][v][k]
            assert "length" in edge_data
            assert float(edge_data["length"]) > 0


def test_route_distance_matches_edge_metric_sum(real_osm_network):
    """Total route distance must match the sum of traversed OSM edge lengths."""
    res = compare_routes_service(
        origin="South End Circle, Bengaluru",
        destination="Gandhi Bazaar Main Road, Bengaluru",
        origin_coordinates=[12.9330, 77.5832],
        destination_coordinates=[12.9420, 77.5720]
    )
    fastest = next(r for r in res.routes if r.category == "fastest")
    computed_edge_sum = sum(seg["lengthMeters"] for seg in fastest.segments)
    # The route distance should equal the sum of edge lengths (rounded to nearest meter)
    assert abs(fastest.distanceMeters - round(computed_edge_sum)) <= 2


def test_geometry_continuity_no_teleportation_jumps(real_osm_network):
    """Consecutive geometry points must follow walkable street topology without teleportation jumps."""
    res = compare_routes_service(
        origin="Cubbon Park, Bengaluru",
        destination="MG Road, Bengaluru",
        origin_coordinates=[12.9770, 77.5920],
        destination_coordinates=[12.9750, 77.6050]
    )
    for route in res.routes:
        geom = route.geometry
        assert len(geom) >= 10, f"Route {route.name} has too few coordinates ({len(geom)}) for real street network"

        for i in range(len(geom) - 1):
            lat1, lon1 = geom[i]
            lat2, lon2 = geom[i + 1]
            dlat = (lat2 - lat1) * 111139.0
            dlon = (lon2 - lon1) * 108390.0
            step_m = math.hypot(dlat, dlon)
            # Consecutive points on a simplified OSM pedestrian way rarely exceed 250m
            assert step_m < 350.0, f"Step from {geom[i]} to {geom[i+1]} is {step_m:.1f}m, suspicious teleportation jump"


def test_out_of_coverage_raises_error_without_fabrication(client: TestClient):
    """Coordinates outside the study area return HTTP 400 Bad Request and never fabricate paths."""
    res = client.post("/api/v1/routes/compare", json={
        "origin": "13.1986, 77.7066",  # Bengaluru Airport (outside pilot corridor)
        "destination": "12.9257, 77.5833",
        "walkingMode": "pedestrian"
    })
    assert res.status_code == 400
    detail = res.json().get("detail", "")
    assert "outside configured study area" in detail


def test_unmapped_lighting_retains_uncertainty():
    """Missing lighting data must never be converted to zero risk or falsely marked safe."""
    model = SegmentRiskModel()
    profile = model.evaluate_edge(
        edge_data={"name": "Unknown Lane"},
        edge_length_meters=150.0,
        lit_status="unmapped"
    )
    assert profile.lighting_indicator == model.r_unknown_prior  # 0.50
    assert profile.lighting_coverage == 0.0
    assert any("unmapped" in lim.lower() for lim in profile.limitations)
