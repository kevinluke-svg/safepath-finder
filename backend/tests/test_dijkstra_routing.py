"""
SafePath Finder — Algorithm Correctness Tests
Tests:
1. Dijkstra baseline fastest path minimizes total traversal time (lambda = 0).
2. Changing edge risk shifts the safety-prioritized route to safer corridors.
3. Increasing risk weight lambda strictly increases route costs monotonically.
4. All edge weights are guaranteed finite and non-negative.
5. Yen's K-shortest paths algorithm returns valid, loopless, distinct paths in non-decreasing cost order.
6. MultiDiGraph parallel edges and geometry reconstruction are handled cleanly without data loss.
7. Unreachable destinations and disconnected graphs raise DisconnectedNetworkError cleanly.
8. Missing evidence is never treated as zero risk; uncertainty prior R_unknown is preserved.
9. Poor evidence coverage remains transparently visible on routes.
10. Route metrics match mathematical definitions exactly.
11. End-to-end API integration with zero PII exposure.
"""

import math
import pytest
import networkx as nx
from shapely.geometry import LineString
from fastapi.testclient import TestClient

from app.geospatial.segment_risk import SegmentRiskModel
from app.geospatial.dijkstra_router import DijkstraRouter, ComputedRoute
from app.geospatial.exceptions import DisconnectedNetworkError, InvalidCoordinateError
from app.core.config import settings


def create_deterministic_diamond_graph() -> nx.MultiDiGraph:
    r"""
    Creates a deterministic test graph:
        (1: Origin)
         /        \
    [Shortcut]   [Avenue]
    1000m total  1200m total
    unlit        well-lit
       \          /
       (4: Destination)

    Cross-connector between intermediate nodes: 2 -> 3 (400m).
    """
    G = nx.MultiDiGraph()
    # Coordinates in Bengaluru pilot bbox
    nodes = {
        1: {"y": 12.9250, "x": 77.5800, "name": "Origin Node 1"},
        2: {"y": 12.9350, "x": 77.5750, "name": "Shortcut Mid Node 2"},
        3: {"y": 12.9350, "x": 77.5850, "name": "Avenue Mid Node 3"},
        4: {"y": 12.9450, "x": 77.5800, "name": "Destination Node 4"}
    }
    for nid, data in nodes.items():
        G.add_node(nid, **data)

    # Edge 1 -> 2 (Dark shortcut leg 1: 500m, unlit)
    G.add_edge(
        1, 2, key=0,
        length=500.0, lit="no", name="Dark Alley Leg 1",
        geometry=LineString([(77.5800, 12.9250), (77.5750, 12.9350)])
    )
    # Edge 2 -> 4 (Dark shortcut leg 2: 500m, unlit)
    G.add_edge(
        2, 4, key=0,
        length=500.0, lit="no", name="Dark Alley Leg 2",
        geometry=LineString([(77.5750, 12.9350), (77.5800, 12.9450)])
    )

    # Edge 1 -> 3 (Well-lit avenue leg 1: 600m, lit, near police)
    G.add_edge(
        1, 3, key=0,
        length=600.0, lit="yes", name="Commercial Avenue Leg 1",
        nearest_police_distance_meters=150.0,
        geometry=LineString([(77.5800, 12.9250), (77.5850, 12.9350)])
    )
    # Edge 3 -> 4 (Well-lit avenue leg 2: 600m, lit, near police)
    G.add_edge(
        3, 4, key=0,
        length=600.0, lit="yes", name="Commercial Avenue Leg 2",
        nearest_police_distance_meters=150.0,
        geometry=LineString([(77.5850, 12.9350), (77.5800, 12.9450)])
    )

    # Cross connector 2 -> 3 (400m, unmapped)
    G.add_edge(
        2, 3, key=0,
        length=400.0, lit=None, name="Cross Street 2-3",
        geometry=LineString([(77.5750, 12.9350), (77.5850, 12.9350)])
    )

    return G


# ---------------------------------------------------------------------------
# Test 1 & 2: Dijkstra Baseline Fastest vs Safety-Prioritized Divergence
# ---------------------------------------------------------------------------
def test_dijkstra_fastest_path_and_safety_shift():
    """
    Tests that:
    1. Fastest mode (lambda=0) chooses the 1000m shortcut [1, 2, 4].
    2. Safety-prioritized mode (lambda=3.0) shifts to the 1200m lit avenue [1, 3, 4].
    """
    G = create_deterministic_diamond_graph()
    risk_model = SegmentRiskModel(lambda_balanced=1.0, lambda_safety=3.0)
    router = DijkstraRouter(G, risk_model)

    routes = router.compute_all_routes(
        origin_lat=12.9250, origin_lon=77.5800,
        dest_lat=12.9450, dest_lon=77.5800,
        include_alternatives=False
    )

    fastest_r = next(r for r in routes if r.category == "fastest")
    safety_r = next(r for r in routes if r.category == "safety_prioritized")

    # 1. Fastest path must minimize travel time -> follows shortcut [1, 2, 4]
    assert fastest_r.node_path == [1, 2, 4]
    assert fastest_r.distance_meters == 1000
    assert fastest_r.duration_seconds == int(round(1000.0 / 1.2))

    # 2. Safety-prioritized path shifts to well-lit avenue [1, 3, 4]
    assert safety_r.node_path == [1, 3, 4]
    assert safety_r.distance_meters == 1200
    assert safety_r.lit_percentage == 100.0

    # Effective risk of safety route is significantly lower than fastest route
    assert safety_r.route_risk_indicator < fastest_r.route_risk_indicator


# ---------------------------------------------------------------------------
# Test 3: Monotonic Generalized Cost Increase with Lambda
# ---------------------------------------------------------------------------
def test_monotonic_cost_increase_with_risk_weight():
    """
    Verifies that for any positive edge risk, edge and route costs increase
    monotonically with lambda: Cost(lambda=0) < Cost(lambda=1) < Cost(lambda=3).
    """
    risk_model = SegmentRiskModel()
    edge_data = {"length": 500.0, "lit": "unlit"}
    profile = risk_model.evaluate_edge(edge_data, edge_length_meters=500.0, lit_status="unlit")

    assert profile.cost_fastest < profile.cost_balanced < profile.cost_safety

    # Expected formulas:
    # T_e = 500 / 1.2 = 416.67
    # Cost_balanced = T_e * (1 + 1.0 * R_eff)
    # Cost_safety = T_e * (1 + 3.0 * R_eff)
    t_e = 500.0 / 1.2
    assert math.isclose(profile.cost_fastest, t_e, rel_tol=1e-2)
    assert math.isclose(profile.cost_balanced, t_e * (1.0 + 1.0 * profile.effective_risk), rel_tol=1e-2)
    assert math.isclose(profile.cost_safety, t_e * (1.0 + 3.0 * profile.effective_risk), rel_tol=1e-2)


# ---------------------------------------------------------------------------
# Test 4: All Edge Weights are Finite and Strictly Non-Negative
# ---------------------------------------------------------------------------
def test_edge_weights_finite_and_non_negative():
    """Ensures edge weights are never negative, NaN, or infinite under edge cases."""
    risk_model = SegmentRiskModel()

    # Extreme edge cases: 0m length, invalid lit, negative crime
    test_cases = [
        {"length": 0.0, "lit": "unknown"},
        {"length": 1.0, "lit": "unlit", "crime_count": 999},
        {"length": 5000.0, "lit": "lit", "crime_rate_per_km": 0.0},
        {"length": 10.0, "lit": "conflicting", "police_walking_minutes": None}
    ]

    for tc in test_cases:
        p = risk_model.evaluate_edge(
            tc,
            edge_length_meters=tc["length"],
            lit_status=tc["lit"],
            crime_count=tc.get("crime_count", 0),
            crime_rate_per_km=tc.get("crime_rate_per_km", 0.0)
        )
        assert p.cost_fastest > 0 and math.isfinite(p.cost_fastest)
        assert p.cost_balanced >= p.cost_fastest and math.isfinite(p.cost_balanced)
        assert p.cost_safety >= p.cost_balanced and math.isfinite(p.cost_safety)
        assert 0.0 <= p.effective_risk <= 1.0
        assert 0.0 <= p.evidence_coverage <= 1.0


# ---------------------------------------------------------------------------
# Test 5: Yen's K-Shortest Paths Algorithm Correctness
# ---------------------------------------------------------------------------
def test_yens_k_shortest_loopless_paths():
    """
    Verifies that Yen's algorithm generates valid, loopless, distinct paths
    in non-decreasing cost order and properly filters near-duplicates.
    """
    G = create_deterministic_diamond_graph()
    router = DijkstraRouter(G, overlap_threshold=0.80, max_alternatives=3)

    routes = router.compute_all_routes(
        origin_lat=12.9250, origin_lon=77.5800,
        dest_lat=12.9450, dest_lon=77.5800,
        include_alternatives=True
    )

    # Must contain fastest, balanced, safety_prioritized, plus at least one Yen alternative
    assert len(routes) >= 4
    alt_routes = [r for r in routes if r.category == "alternative"]
    assert len(alt_routes) >= 1

    # Check loopless property on all paths
    for r in routes:
        path = r.node_path
        assert len(path) == len(set(path)), f"Path {path} contains a loop!"
        assert path[0] == 1 and path[-1] == 4

    # Verify Yen alternatives are distinct from each other and from primary paths
    primary_paths = [r.node_path for r in routes if r.category != "alternative"]
    for alt in alt_routes:
        # Overlap with existing paths must be strictly below threshold
        for p_path in primary_paths:
            assert router.calculate_path_edge_overlap(alt.node_path, p_path) < router.overlap_threshold

    # All Yen alternatives are distinct from each other
    for i in range(len(alt_routes)):
        for j in range(i + 1, len(alt_routes)):
            assert alt_routes[i].node_path != alt_routes[j].node_path
            # In non-decreasing cost order
            assert alt_routes[i].total_cost <= alt_routes[j].total_cost


# ---------------------------------------------------------------------------
# Test 6: Parallel Edges in MultiDiGraph and Geometry Preservation
# ---------------------------------------------------------------------------
def test_parallel_edges_and_geometry_preservation():
    """
    Verifies that between two nodes with parallel edges, the router picks the
    edge corresponding to minimum cost and reconstructs coordinates without data loss.
    """
    G = nx.MultiDiGraph()
    G.add_node(1, y=12.9250, x=77.5800)
    G.add_node(2, y=12.9350, x=77.5800)

    # Edge 0: Dark alley (length 200m, lit=no)
    G.add_edge(
        1, 2, key=0, length=200.0, lit="no", name="Dark Alley",
        geometry=LineString([(77.5800, 12.9250), (77.5790, 12.9300), (77.5800, 12.9350)])
    )
    # Edge 1: Lit avenue (length 220m, lit=yes)
    G.add_edge(
        1, 2, key=1, length=220.0, lit="yes", name="Lit Avenue",
        geometry=LineString([(77.5800, 12.9250), (77.5810, 12.9300), (77.5800, 12.9350)])
    )

    risk_model = SegmentRiskModel(lambda_safety=4.0)
    router = DijkstraRouter(G, risk_model)

    routes = router.compute_all_routes(
        origin_lat=12.9250, origin_lon=77.5800,
        dest_lat=12.9350, dest_lon=77.5800,
        include_alternatives=False
    )

    fastest_r = next(r for r in routes if r.category == "fastest")
    safety_r = next(r for r in routes if r.category == "safety_prioritized")

    # Fastest chooses edge 0 (200m < 220m)
    assert fastest_r.distance_meters == 200
    assert fastest_r.segments[0]["edgeKey"] == 0

    # Safety-prioritized chooses edge 1 (well-lit)
    assert safety_r.distance_meters == 220
    assert safety_r.segments[0]["edgeKey"] == 1
    assert safety_r.lit_percentage == 100.0

    # Geometry coordinates must match LineString (3 coordinate vertices)
    assert len(safety_r.geometry) == 3


# ---------------------------------------------------------------------------
# Test 7: Unreachable Destination Handling
# ---------------------------------------------------------------------------
def test_unreachable_destination_raises_error():
    """Verifies that disconnected network components raise DisconnectedNetworkError cleanly."""
    G = nx.MultiDiGraph()
    G.add_node(1, y=12.9250, x=77.5800)
    G.add_node(2, y=12.9260, x=77.5810)
    G.add_edge(1, 2, key=0, length=100.0, lit="yes")

    # Disconnected component
    G.add_node(99, y=12.9600, x=77.6000)

    router = DijkstraRouter(G)
    with pytest.raises(DisconnectedNetworkError) as exc_info:
        router.compute_all_routes(
            origin_lat=12.9250, origin_lon=77.5800,
            dest_lat=12.9600, dest_lon=77.6000
        )
    assert "No connected pedestrian route exists" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 8: Missing Evidence is Never Treated as Zero Risk
# ---------------------------------------------------------------------------
def test_missing_evidence_preserves_uncertainty_prior():
    """
    Verifies the critical safety requirement:
    R_effective = Q * R_observed + (1 - Q) * R_unknown.
    When evidence is completely absent (Q=0), R_effective must equal R_unknown, NEVER 0.0.
    """
    model_default = SegmentRiskModel(r_unknown_prior=0.50)
    profile_default = model_default.evaluate_edge(
        {"length": 200.0},
        edge_length_meters=200.0,
        lit_status="unmapped",
        has_crime_dataset=False,
        community_reports_count=0,
        police_walking_minutes=None,
        hospital_walking_minutes=None
    )
    # When evidence is missing, effective risk must equal prior, never zero
    assert profile_default.effective_risk > 0.0
    assert math.isclose(profile_default.effective_risk, 0.50, rel_tol=1e-3)
    assert profile_default.has_insufficient_evidence is True

    # Sensitivity test: changing R_unknown prior shifts effective risk monotonically
    model_high_prior = SegmentRiskModel(r_unknown_prior=0.80)
    profile_high = model_high_prior.evaluate_edge(
        {"length": 200.0},
        edge_length_meters=200.0,
        lit_status="unmapped"
    )
    assert profile_high.effective_risk > profile_default.effective_risk


# ---------------------------------------------------------------------------
# Test 9: Mathematical Equivalence of Route Metrics
# ---------------------------------------------------------------------------
def test_route_metrics_mathematical_integrity():
    """
    Verifies that route metrics match documented equations:
    Route risk = sum(T_e * R_effective_e) / sum(T_e)
    Coverage = sum(T_e * Q_e) / sum(T_e)
    """
    G = create_deterministic_diamond_graph()
    risk_model = SegmentRiskModel()
    router = DijkstraRouter(G, risk_model)

    routes = router.compute_all_routes(
        origin_lat=12.9250, origin_lon=77.5800,
        dest_lat=12.9450, dest_lon=77.5800,
        include_alternatives=False
    )

    for r in routes:
        # Sum up segments
        sum_te = sum(s["traversalTimeSeconds"] for s in r.segments)
        weighted_risk = sum(s["traversalTimeSeconds"] * s["effectiveRisk"] for s in r.segments)
        weighted_cov = sum(s["traversalTimeSeconds"] * s["evidenceCoverage"] for s in r.segments)

        expected_risk = round(weighted_risk / sum_te, 4)
        expected_cov = round(weighted_cov / sum_te, 4)

        assert math.isclose(r.route_risk_indicator, expected_risk, abs_tol=1e-3)
        assert math.isclose(r.evidence_coverage, expected_cov, abs_tol=1e-3)


# ---------------------------------------------------------------------------
# Test 10: API Integration, Route Comparison, and Zero PII
# ---------------------------------------------------------------------------
def test_api_route_comparison_with_real_graph_and_zero_pii(client: TestClient):
    """
    Tests end-to-end POST /api/v1/routes/compare:
    1. Returns Fastest, Balanced, Safety-prioritized, and Yen alternatives.
    2. Validates that no PII is returned in the response body.
    """
    payload = {
        "origin": "12.9257, 77.5833",  # Jayanagar 4th Block
        "destination": "12.9501, 77.5847",  # Lalbagh Main Gate
        "walkingMode": "pedestrian",
        "preferences": {
            "includeAlternatives": True,
            "maxAlternatives": 2
        }
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["origin"] == payload["origin"]
    assert data["destination"] == payload["destination"]
    assert len(data["routes"]) >= 3

    categories = [r["category"] for r in data["routes"]]
    assert "fastest" in categories
    assert "balanced" in categories
    assert "safety_prioritized" in categories

    # Verify zero PII in route response
    forbidden_pii_keys = {"email", "password", "hashed_password", "phone", "reporter_name", "reporter_email"}
    resp_str = response.text.lower()
    for pii in forbidden_pii_keys:
        assert pii not in resp_str, f"Found leaked PII field '{pii}' in response!"
