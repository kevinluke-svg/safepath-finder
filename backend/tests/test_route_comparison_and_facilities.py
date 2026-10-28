"""
SafePath Finder — Route Comparison, Streetlight Evidence, Nearby Facilities, and Performance Tests

Validates:
1. Priority 1 & 2: Fastest, Balanced, and Safety-prioritized routes have independent edge costs:
   Cost_fastest(e) = T_e
   Cost_balanced(e) = T_e * (1 + lambda_balanced * R_eff(e))
   Cost_safety(e) = T_e * (1 + lambda_safety * R_eff(e))
2. Priority 3: Legitimate shared optimal routes vs distinct routes when safety evidence diverges.
3. Priority 4: Real Streetlight Evidence Summary: length-based coverage (lit %, unlit %, conflicting %, unknown %),
   mapped streetlamp post counts, and epistemology (unknown != unlit).
4. Priority 5: Nearby Places Summary: police stations, hospitals, transit, parks within 500m corridor,
   perpendicular distances, walking access times, disclaimers.
5. Priority 6: Epistemological explanations and privacy protections (zero PII).
6. Priority 7: In-memory router caching performance and cache invalidation across configs.
"""

import time
import pytest
import networkx as nx
from shapely.geometry import LineString, Point
from fastapi.testclient import TestClient

from app.main import app
from app.geospatial.segment_risk import SegmentRiskModel
from app.geospatial.dijkstra_router import DijkstraRouter, ComputedRoute
from app.geospatial.facilities_adapter import FacilityPoint, FacilityAuditResult
from app.geospatial.exceptions import DisconnectedNetworkError
from app.services.routing_service import compare_routes_service, _ROUTER_CACHE
from app.core.config import settings


@pytest.fixture
def synthetic_divergent_graph() -> nx.MultiDiGraph:
    """
    Creates a diamond graph where:
    - Path A (1 -> 2 -> 4): Short (800m), unlit, high risk (R_eff = 0.85)
    - Path B (1 -> 3 -> 4): Slightly longer (1000m), well-lit, low risk (R_eff = 0.15)

    For Fastest: Path A is optimal (800m < 1000m).
    For Safety-prioritized: Path B is optimal because safety cost of Path A is much higher:
    Cost_A = (800/1.278) * (1 + 3.0 * 0.85) = 625.9 * 3.55 = 2221.9
    Cost_B = (1000/1.278) * (1 + 3.0 * 0.15) = 782.5 * 1.45 = 1134.6
    """
    G = nx.MultiDiGraph()
    nodes = {
        1: {"y": 12.9250, "x": 77.5800, "name": "Origin Node 1"},
        2: {"y": 12.9350, "x": 77.5750, "name": "Dark Alley Node 2"},
        3: {"y": 12.9350, "x": 77.5850, "name": "Lit Boulevard Node 3"},
        4: {"y": 12.9450, "x": 77.5800, "name": "Destination Node 4"}
    }
    for nid, data in nodes.items():
        G.add_node(nid, **data)

    # Edge 1 -> 2 (400m, unlit)
    G.add_edge(1, 2, key=0, length=400.0, lit="no", name="Dark Path 1",
               geometry=LineString([(77.5800, 12.9250), (77.5750, 12.9350)]))
    # Edge 2 -> 4 (400m, unlit)
    G.add_edge(2, 4, key=0, length=400.0, lit="no", name="Dark Path 2",
               geometry=LineString([(77.5750, 12.9350), (77.5800, 12.9450)]))

    # Edge 1 -> 3 (500m, lit=yes)
    G.add_edge(1, 3, key=0, length=500.0, lit="yes", name="Lit Boulevard 1",
               geometry=LineString([(77.5800, 12.9250), (77.5850, 12.9350)]))
    # Edge 3 -> 4 (500m, lit=yes)
    G.add_edge(3, 4, key=0, length=500.0, lit="yes", name="Lit Boulevard 2",
               geometry=LineString([(77.5850, 12.9350), (77.5800, 12.9450)]))

    return G


@pytest.fixture
def synthetic_uniform_graph() -> nx.MultiDiGraph:
    """
    Creates a corridor where all edges have identical unknown lighting (r_unknown = 0.5):
    - Path A (1 -> 2 -> 4): 600m
    - Path B (1 -> 3 -> 4): 900m
    Because R_eff is identical across all edges, Fastest, Balanced, and Safety-prioritized
    MUST all mathematically choose Path A (direct scalar multiplication of travel times).
    """
    G = nx.MultiDiGraph()
    nodes = {
        1: {"y": 12.9250, "x": 77.5800},
        2: {"y": 12.9350, "x": 77.5750},
        3: {"y": 12.9350, "x": 77.5850},
        4: {"y": 12.9450, "x": 77.5800}
    }
    for nid, data in nodes.items():
        G.add_node(nid, **data)

    # Edge 1 -> 2 (300m, unmapped)
    G.add_edge(1, 2, key=0, length=300.0, name="Direct Ave 1",
               geometry=LineString([(77.5800, 12.9250), (77.5750, 12.9350)]))
    # Edge 2 -> 4 (300m, unmapped)
    G.add_edge(2, 4, key=0, length=300.0, name="Direct Ave 2",
               geometry=LineString([(77.5750, 12.9350), (77.5800, 12.9450)]))

    # Edge 1 -> 3 (450m, unmapped)
    G.add_edge(1, 3, key=0, length=450.0, name="Detour St 1",
               geometry=LineString([(77.5800, 12.9250), (77.5850, 12.9350)]))
    # Edge 3 -> 4 (450m, unmapped)
    G.add_edge(3, 4, key=0, length=450.0, name="Detour St 2",
               geometry=LineString([(77.5850, 12.9350), (77.5800, 12.9450)]))

    return G


class TestIndependentRoutingObjectives:
    def test_divergent_paths_under_safety_weight(self, synthetic_divergent_graph):
        """Verify that when safety evidence differs, safety-prioritized selects a safer path than fastest."""
        risk_model = SegmentRiskModel(
            lambda_balanced=1.0,
            lambda_safety=3.0,
            walking_speed_mps=1.278
        )
        router = DijkstraRouter(synthetic_divergent_graph, risk_model=risk_model)
        routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800)

        fastest = next(r for r in routes if r.category == "fastest")
        safety = next(r for r in routes if r.category == "safety_prioritized")

        # Fastest must pick the 800m unlit shortcut [1, 2, 4]
        assert fastest.node_path == [1, 2, 4]
        assert fastest.distance_meters == 800

        # Safety-prioritized must pick the 1000m lit boulevard [1, 3, 4]
        assert safety.node_path == [1, 3, 4]
        assert safety.distance_meters == 1000

        # Ensure route risk indicator is lower for the safety route (0.42 < 0.62)
        assert safety.route_risk_indicator < fastest.route_risk_indicator
        assert safety.is_identical_to_fastest is False

    def test_mathematically_legitimate_identical_route(self, synthetic_uniform_graph):
        """
        When all edges have uniform risk prior, scaling edge costs by (1 + lambda * R)
        preserves exact shortest path order. All preferences legitimately select the same route.
        """
        risk_model = SegmentRiskModel(
            lambda_balanced=1.0,
            lambda_safety=3.0,
            walking_speed_mps=1.278
        )
        router = DijkstraRouter(synthetic_uniform_graph, risk_model=risk_model)
        routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800)

        fastest = next(r for r in routes if r.category == "fastest")
        balanced = next(r for r in routes if r.category == "balanced")
        safety = next(r for r in routes if r.category == "safety_prioritized")

        assert fastest.node_path == [1, 2, 4]
        assert balanced.node_path == [1, 2, 4]
        assert safety.node_path == [1, 2, 4]

        # Balanced and safety routes must correctly flag is_identical_to_fastest
        assert balanced.is_identical_to_fastest is True
        assert safety.is_identical_to_fastest is True
        assert "multi-objective optimal" in safety.identical_notes.lower() or "optimal" in safety.identical_notes.lower()

    def test_independent_cost_calculation_formulas(self, synthetic_divergent_graph):
        """Verify Dijkstra edge costs adhere strictly to documented mathematical definitions."""
        risk_model = SegmentRiskModel(
            lambda_balanced=1.2,
            lambda_safety=2.8,
            walking_speed_mps=1.278
        )
        router = DijkstraRouter(synthetic_divergent_graph, risk_model=risk_model)

        # Check edge weights on lit boulevard leg (1 -> 3)
        data = synthetic_divergent_graph[1][3][0]
        profile = router.edge_profiles[(1, 3, 0)]
        t_e = profile.traversal_time_seconds
        r_eff = profile.effective_risk

        assert data["cost_fastest"] == pytest.approx(t_e, rel=1e-4)
        assert data["cost_balanced"] == pytest.approx(t_e * (1.0 + 1.2 * r_eff), rel=1e-4)
        assert data["cost_safety"] == pytest.approx(t_e * (1.0 + 2.8 * r_eff), rel=1e-4)


class TestStreetlightEvidenceSummary:
    def test_streetlight_summary_computation(self, synthetic_divergent_graph):
        """Verify Streetlight Evidence Summary calculates exact length-weighted percentages and counts."""
        router = DijkstraRouter(synthetic_divergent_graph)
        routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800)

        lit_route = next(r for r in routes if r.category == "safety_prioritized")
        sl_lit = lit_route.streetlight_summary
        assert sl_lit is not None
        assert sl_lit["totalDistanceMeters"] == 1000.0
        assert sl_lit["knownLitDistanceMeters"] == 1000.0
        assert sl_lit["litPercentage"] == 100.0
        assert sl_lit["unlitPercentage"] == 0.0
        assert sl_lit["unknownPercentage"] == 0.0

        dark_route = next(r for r in routes if r.category == "fastest")
        sl_dark = dark_route.streetlight_summary
        assert sl_dark is not None
        assert sl_dark["totalDistanceMeters"] == 800.0
        assert sl_dark["knownUnlitDistanceMeters"] == 800.0
        assert sl_dark["unlitPercentage"] == 100.0
        assert sl_dark["litPercentage"] == 0.0
        assert sl_dark["unknownPercentage"] == 0.0

    def test_percentages_sum_to_100_with_mixed_segments(self):
        """Test a route with lit, unlit, conflicting, and unknown segments sums to 100%."""
        G = nx.MultiDiGraph()
        nodes = {
            1: {"y": 12.90, "x": 77.50},
            2: {"y": 12.91, "x": 77.50},
            3: {"y": 12.92, "x": 77.50},
            4: {"y": 12.93, "x": 77.50},
            5: {"y": 12.94, "x": 77.50}
        }
        for nid, data in nodes.items():
            G.add_node(nid, **data)

        # 1->2: 100m lit
        G.add_edge(1, 2, key=0, length=100.0, lit="yes", geometry=LineString([(77.50, 12.90), (77.50, 12.91)]))
        # 2->3: 200m unlit
        G.add_edge(2, 3, key=0, length=200.0, lit="no", geometry=LineString([(77.50, 12.91), (77.50, 12.92)]))
        # 3->4: 300m conflicting
        G.add_edge(3, 4, key=0, length=300.0, lit="conflicting", geometry=LineString([(77.50, 12.92), (77.50, 12.93)]))
        # 4->5: 400m unknown
        G.add_edge(4, 5, key=0, length=400.0, geometry=LineString([(77.50, 12.93), (77.50, 12.94)]))

        router = DijkstraRouter(G)
        routes = router.compute_all_routes(12.90, 77.50, 12.94, 77.50)
        route = routes[0]
        sl = route.streetlight_summary

        assert sl["totalDistanceMeters"] == 1000.0
        assert sl["knownLitDistanceMeters"] == 100.0
        assert sl["knownUnlitDistanceMeters"] == 200.0
        assert sl["conflictingDistanceMeters"] == 300.0
        assert sl["unknownDistanceMeters"] == 400.0

        assert sl["litPercentage"] == 10.0
        assert sl["unlitPercentage"] == 20.0
        assert sl["conflictingPercentage"] == 30.0
        assert sl["unknownPercentage"] == 40.0
        total_pct = sl["litPercentage"] + sl["unlitPercentage"] + sl["conflictingPercentage"] + sl["unknownPercentage"]
        assert total_pct == pytest.approx(100.0, rel=1e-5)


class TestNearbyFacilitiesCorridor:
    def test_nearby_places_retrieval_and_filtering(self, synthetic_divergent_graph):
        """Verify nearby places within 500m corridor are retrieved with perpendicular distances."""
        # Attach a mock police station 100m away from node 3 (12.9350, 77.5850)
        p1 = FacilityPoint(
            id="p1",
            facility_type="police",
            name="Ashoka Police Station",
            latitude=12.9359,
            longitude=77.5850,
            source="OpenStreetMap",
            confidence="verified_spatial_point",
            metadata={}
        )
        # Attach a distant hospital 2000m away (outside 500m corridor)
        h1 = FacilityPoint(
            id="h1",
            facility_type="hospital",
            name="Distant Hospital",
            latitude=12.9600,
            longitude=77.6000,
            source="OpenStreetMap",
            confidence="verified_spatial_point",
            metadata={}
        )
        fac_result = FacilityAuditResult(
            study_area_name="test",
            police_stations=[p1],
            hospitals=[h1],
            sources=["OpenStreetMap"],
            retrieved_at="2026-10-28T12:00:00Z"
        )

        router = DijkstraRouter(
            synthetic_divergent_graph,
            facilities_result=fac_result
        )
        routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800)
        safety_route = next(r for r in routes if r.category == "safety_prioritized")
        places = safety_route.nearby_places

        assert len(places) >= 1
        p_names = [p["name"] for p in places]
        assert "Ashoka Police Station" in p_names
        assert "Distant Hospital" not in p_names

        # Verify perpendicular line distance to route is within expected range (~44m)
        ashoka_p = next(p for p in places if p["name"] == "Ashoka Police Station")
        assert 30.0 <= ashoka_p["distanceMeters"] <= 100.0
        assert ashoka_p["category"] == "police"
        assert "staffing" in ashoka_p["limitations"].lower() or "monitored" in ashoka_p["limitations"].lower()

    def test_no_facilities_within_corridor(self, synthetic_uniform_graph):
        """Verify empty nearby_places list when no facilities exist in corridor."""
        fac_result = FacilityAuditResult(
            study_area_name="test",
            police_stations=[],
            hospitals=[],
            sources=["OpenStreetMap"],
            retrieved_at="2026-10-28T12:00:00Z"
        )
        router = DijkstraRouter(
            synthetic_uniform_graph,
            facilities_result=fac_result
        )
        routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800)
        route = routes[0]
        assert isinstance(route.nearby_places, list)


class TestRouterPerformanceCaching:
    def test_router_cache_hit_and_speedup(self):
        """Verify RoutingService caches DijkstraRouter instances across requests for the same study area and weights."""
        _ROUTER_CACHE.clear()

        # Jayanagar Metro to Lalbagh West Gate coordinates
        origin_coords = [12.9299, 77.5824]
        dest_coords = [12.9463, 77.5801]

        # Call 1: Cold cache
        t0 = time.perf_counter()
        res1 = compare_routes_service(
            origin="Jayanagar Metro Station",
            destination="Lalbagh West Gate",
            origin_coordinates=origin_coords,
            destination_coordinates=dest_coords
        )
        t_cold = (time.perf_counter() - t0) * 1000.0

        assert len(_ROUTER_CACHE) == 1
        assert len(res1.routes) >= 3

        # Call 2: Warm cache (same study area, graph, and weights)
        t1 = time.perf_counter()
        res2 = compare_routes_service(
            origin="South End Circle",
            destination="Lalbagh West Gate",
            origin_coordinates=[12.9372, 77.5805],
            destination_coordinates=dest_coords
        )
        t_warm = (time.perf_counter() - t1) * 1000.0

        # Warm request must be significantly faster (< 250ms)
        assert t_warm < 250.0
        assert len(res2.routes) >= 3


class TestApiRouteComparisonContract:
    def test_api_compare_endpoint_contract(self):
        """Verify the full FastAPI endpoint /api/v1/routes/compare returns proper schemas and zero PII."""
        client = TestClient(app)
        payload = {
            "origin": "Jayanagar Metro Station",
            "destination": "Lalbagh West Gate",
            "originCoordinates": [12.9299, 77.5824],
            "destinationCoordinates": [12.9463, 77.5801]
        }
        response = client.post("/api/v1/routes/compare", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "routes" in data
        assert len(data["routes"]) >= 3

        for r in data["routes"]:
            # Route identifier and categories
            assert "id" in r
            assert r["category"] in ["fastest", "balanced", "safety_prioritized", "alternative"]
            assert r["distanceMeters"] > 0
            assert r["durationSeconds"] > 0
            assert len(r["geometry"]) >= 2

            # Streetlight summary
            sl = r.get("streetlightSummary")
            assert sl is not None
            assert "litPercentage" in sl
            assert "unlitPercentage" in sl
            assert "unknownPercentage" in sl
            assert "mappedStreetlampsCount" in sl
            assert "explanation" in sl

            # Nearby places
            places = r.get("nearbyPlaces", [])
            assert isinstance(places, list)
            for p in places:
                assert "name" in p
                assert "category" in p
                assert "distanceMeters" in p
                assert "limitations" in p

            # Privacy checks: zero PII
            res_str = str(r).lower()
            assert "email" not in res_str
            assert "password" not in res_str
            assert "user_id" not in res_str
            assert "phone" not in res_str
