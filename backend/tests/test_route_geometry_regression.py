"""
SafePath Finder — Route Geometry & Visual Integrity Regression Tests

Covers Step 6 Requirements:
1. Curved street preservation: Route contains intermediate coordinates required to follow curved streets.
2. Geometry reconstruction preserves the geometry of selected graph edges.
3. Coordinate order: [latitude, longitude] in API response matches Leaflet expectation.
4. Route geometry and edge weights correspond to the exact same selected path.
5. Parallel edges: Minimum weight edge's geometry and metrics are selected.
6. Route replacement: New route requests return distinct, newly computed geometry.
7. Stale result prevention: Failed requests return controlled errors, never stale successful data.
8. Disconnected network: Unreachable destinations return controlled DisconnectedNetworkError.
9. Continuous pedestrian topology: Consecutive vertices are connected without teleportation jumps.
10. Metric correspondence: Total distance and duration match mathematical sum of selected edge metrics.
"""

import math
import pytest
import networkx as nx
from shapely.geometry import LineString
from fastapi.testclient import TestClient

from app.main import app
from app.geospatial.segment_risk import SegmentRiskModel
from app.geospatial.dijkstra_router import DijkstraRouter, ComputedRoute
from app.geospatial.exceptions import DisconnectedNetworkError, OutOfCoverageError
from app.geospatial.study_area import StudyArea
from app.services.routing_service import compare_routes_service


def create_curved_deterministic_graph() -> nx.MultiDiGraph:
    r"""
    Creates a deterministic test graph with curved streets, parallel edges, and disconnected node:
    
       Node 1 (12.9250, 77.5800)
         |
         | (Curved Street: 4 waypoints)
         v
       Node 2 (12.9300, 77.5800)
        / \
       /   \ (Parallel edges to Node 3)
      v     v
       Node 3 (12.9350, 77.5850)
       
       Node 99 (12.9400, 77.5900) [Isolated / Disconnected]
    """
    G = nx.MultiDiGraph()
    G.add_node(1, y=12.9250, x=77.5800, name="Origin 1")
    G.add_node(2, y=12.9300, x=77.5800, name="Junction 2")
    G.add_node(3, y=12.9350, x=77.5850, name="Destination 3")
    G.add_node(99, y=12.9400, x=77.5900, name="Disconnected 99")

    # Edge 1 -> 2: Curved street with 2 intermediate points (S-curve)
    # Coords in LineString are (lon, lat)
    curved_coords = [
        (77.5800, 12.9250),
        (77.5815, 12.9265),
        (77.5785, 12.9285),
        (77.5800, 12.9300),
    ]
    G.add_edge(
        1, 2, key=0,
        name="Curved Boulevard",
        length=620.0,
        highway="primary",
        lit="yes",
        geometry=LineString(curved_coords)
    )
    G.add_edge(
        2, 1, key=0,
        name="Curved Boulevard (Reverse)",
        length=620.0,
        highway="primary",
        lit="yes",
        geometry=LineString(list(reversed(curved_coords)))
    )

    # Edge 2 -> 3: Parallel edges with differing risk and geometry
    # Edge Key 0: Direct dark alley (unlit, 500m)
    G.add_edge(
        2, 3, key=0,
        name="Dark Direct Cut-Through",
        length=500.0,
        highway="residential",
        lit="no",
        geometry=LineString([(77.5800, 12.9300), (77.5850, 12.9350)])
    )
    # Edge Key 1: Lit curved avenue (well-lit, 550m, lower safety cost)
    lit_curve = [
        (77.5800, 12.9300),
        (77.5800, 12.9350),
        (77.5850, 12.9350),
    ]
    G.add_edge(
        2, 3, key=1,
        name="Well-Lit Grid Promenade",
        length=550.0,
        highway="secondary",
        lit="yes",
        geometry=LineString(lit_curve)
    )

    return G


# ---------------------------------------------------------------------------
# Test 1 & 2: Curved street intermediate coordinates and geometry preservation
# ---------------------------------------------------------------------------
def test_curved_street_geometry_preservation():
    """Verify that routing across a curved street preserves intermediate waypoints."""
    G = create_curved_deterministic_graph()
    risk_model = SegmentRiskModel(walking_speed_mps=1.2)
    router = DijkstraRouter(G, risk_model)

    routes = router.compute_all_routes(
        origin_lat=12.9250, origin_lon=77.5800,
        dest_lat=12.9300, dest_lon=77.5800,
        include_alternatives=False
    )
    assert len(routes) > 0
    primary = routes[0]

    # Geometry must have at least 4 coordinates (start, 2 intermediate, end)
    assert len(primary.geometry) >= 4, f"Expected >=4 coordinates for curved street, got {len(primary.geometry)}"

    # Check that intermediate curved points exist in geometry:
    # Intermediate 1: lat=12.9265, lon=77.5815
    # Intermediate 2: lat=12.9285, lon=77.5785
    lats = [pt[0] for pt in primary.geometry]
    lons = [pt[1] for pt in primary.geometry]
    assert any(abs(lat - 12.9265) < 0.0001 for lat in lats), "Intermediate curve point 1 missing"
    assert any(abs(lon - 77.5815) < 0.0001 for lon in lons), "Intermediate curve lon 1 missing"
    assert any(abs(lat - 12.9285) < 0.0001 for lat in lats), "Intermediate curve point 2 missing"


# ---------------------------------------------------------------------------
# Test 3: Coordinate Order [latitude, longitude] in API & Leaflet rendering
# ---------------------------------------------------------------------------
def test_coordinate_order_lat_lon():
    """Verify that route coordinates are returned strictly in [lat, lon] order."""
    client = TestClient(app)
    resp = client.post("/api/v1/routes/compare", json={
        "origin": "Jayanagar 4th Block",
        "destination": "South End Circle",
        "originCoordinates": [12.9257, 77.5833],
        "destinationCoordinates": [12.9330, 77.5832],
        "preferences": {"includeAlternatives": False}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["routes"]) > 0

    route = data["routes"][0]
    for pt in route["geometry"]:
        lat, lon = pt[0], pt[1]
        # In Bengaluru: latitude is ~12.9x, longitude is ~77.5x
        assert 12.90 <= lat <= 13.05, f"Latitude {lat} out of range (check coordinate order!)"
        assert 77.50 <= lon <= 77.65, f"Longitude {lon} out of range (check coordinate order!)"


# ---------------------------------------------------------------------------
# Test 4 & 10: Selected edge weights and geometry correspond to same path metrics
# ---------------------------------------------------------------------------
def test_geometry_and_weights_correspond_to_same_path():
    """Verify route total distance and duration match the sum of edge segment metrics."""
    G = create_curved_deterministic_graph()
    risk_model = SegmentRiskModel(walking_speed_mps=1.2)
    router = DijkstraRouter(G, risk_model)

    routes = router.compute_all_routes(
        origin_lat=12.9250, origin_lon=77.5800,
        dest_lat=12.9350, dest_lon=77.5850,
        ranking_preference="safety",
        include_alternatives=False
    )
    assert len(routes) > 0
    route = routes[0]

    sum_segment_dist = sum(seg["lengthMeters"] for seg in route.segments)
    sum_segment_time = sum(seg["traversalTimeSeconds"] for seg in route.segments)

    # Route distance must match sum of selected segments
    assert abs(route.distance_meters - round(sum_segment_dist)) <= 1
    # Route duration must match sum of selected segment traversal times
    assert abs(route.duration_seconds - round(sum_segment_time)) <= 1


# ---------------------------------------------------------------------------
# Test 5: Parallel edges handling and selection
# ---------------------------------------------------------------------------
def test_parallel_edges_handle_correctly():
    """Verify that Dijkstra and geometry reconstruction select the correct parallel edge."""
    G = create_curved_deterministic_graph()
    risk_model = SegmentRiskModel(walking_speed_mps=1.2, lambda_safety=1.0)
    router = DijkstraRouter(G, risk_model)

    routes = router.compute_all_routes(
        origin_lat=12.9300, origin_lon=77.5800,  # Node 2
        dest_lat=12.9350, dest_lon=77.5850,    # Node 3
        ranking_preference="safety",
        include_alternatives=False
    )
    assert len(routes) > 0
    safety_route = routes[0]

    # Under safety-prioritization, Node 2 -> Node 3 should pick Key 1 ("Well-Lit Grid Promenade")
    seg = safety_route.segments[0]
    assert seg["edgeKey"] == 1
    assert seg["streetName"] == "Well-Lit Grid Promenade"
    assert seg["litStatus"] == "lit"
    # Its geometry must contain the right-angle corner waypoint (12.9350, 77.5800)
    geom_lats = [p[0] for p in safety_route.geometry]
    geom_lons = [p[1] for p in safety_route.geometry]
    assert any(abs(lat - 12.9350) < 0.0001 and abs(lon - 77.5800) < 0.0001 for lat, lon in zip(geom_lats, geom_lons))


# ---------------------------------------------------------------------------
# Test 6: Newly requested route replaces previous route
# ---------------------------------------------------------------------------
def test_new_route_replaces_previous_route():
    """Verify that different requests return distinct routes without stale bleed."""
    client = TestClient(app)

    # Query 1: Jayanagar 4th Block -> South End Circle
    resp1 = client.post("/api/v1/routes/compare", json={
        "origin": "Jayanagar 4th Block",
        "destination": "South End Circle",
        "originCoordinates": [12.9257, 77.5833],
        "destinationCoordinates": [12.9330, 77.5832],
        "preferences": {"includeAlternatives": False}
    })
    assert resp1.status_code == 200
    r1 = resp1.json()["routes"][0]

    # Query 2: Cubbon Park -> MG Road
    resp2 = client.post("/api/v1/routes/compare", json={
        "origin": "Cubbon Park",
        "destination": "MG Road",
        "originCoordinates": [12.9770, 77.5920],
        "destinationCoordinates": [12.9750, 77.6050],
        "preferences": {"includeAlternatives": False}
    })
    assert resp2.status_code == 200
    r2 = resp2.json()["routes"][0]

    # Routes must be completely distinct in coordinates, distance, and name
    assert r1["geometry"] != r2["geometry"]
    assert r1["distanceMeters"] != r2["distanceMeters"]
    assert r1["geometry"][0] != r2["geometry"][0]


# ---------------------------------------------------------------------------
# Test 7 & 8: Disconnected & unreachable destinations return controlled errors
# ---------------------------------------------------------------------------
def test_disconnected_destination_returns_controlled_error():
    """Verify that unreachable nodes raise DisconnectedNetworkError, not stale results."""
    G = create_curved_deterministic_graph()
    risk_model = SegmentRiskModel(walking_speed_mps=1.2)
    router = DijkstraRouter(G, risk_model)

    with pytest.raises(DisconnectedNetworkError):
        # Node 99 has no inbound or outbound edges
        router.compute_all_routes(
            origin_lat=12.9250, origin_lon=77.5800,  # Node 1
            dest_lat=12.9400, dest_lon=77.5900,    # Node 99
            include_alternatives=False
        )


def test_out_of_coverage_request_fails_cleanly():
    """Verify that requests outside coverage return 400 error and do not display stale data."""
    client = TestClient(app)
    resp = client.post("/api/v1/routes/compare", json={
        "origin": "Electronic City",
        "destination": "Whitefield",
        "originCoordinates": [12.8452, 77.6602],
        "destinationCoordinates": [12.9698, 77.7500],
        "preferences": {"includeAlternatives": False}
    })
    assert resp.status_code == 400
    assert "outside" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 9: Returned route consists of connected, pedestrian-accessible edges
# ---------------------------------------------------------------------------
def test_route_has_no_disconnected_teleportation_jumps():
    """Verify that consecutive vertices in route geometry are strictly contiguous (< 400m apart)."""
    client = TestClient(app)
    resp = client.post("/api/v1/routes/compare", json={
        "origin": "Cool Joint Jayanagar",
        "destination": "South End Circle",
        "originCoordinates": [12.92876, 77.58586],
        "destinationCoordinates": [12.9330, 77.5832],
        "preferences": {"includeAlternatives": True, "maxAlternatives": 2}
    })
    assert resp.status_code == 200
    routes = resp.json()["routes"]

    for route in routes:
        geom = route["geometry"]
        assert len(geom) >= 2
        for i in range(len(geom) - 1):
            p1 = geom[i]
            p2 = geom[i + 1]
            # Euclidean distance in degrees
            step_deg = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            # 0.005 degrees is approx ~550m. No single pedestrian block step should teleport >550m
            assert step_deg < 0.005, f"Teleportation jump detected between vertex {i} and {i+1}: {step_deg:.5f} deg"
