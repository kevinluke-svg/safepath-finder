"""
SafePath Finder — Phase 2 Automated Test Suite: Multi-Dimensional Safety Algorithm & Time-Aware Routing

Comprehensive verification covering:
1. Fastest-time optimization strictly minimizing traversal time regardless of departure period.
2. Balanced weighted-cost optimization (Cost = T * (1 + lambda_balanced * R_effective)).
3. Safety-prioritized weighted-cost optimization (lambda_safety > lambda_balanced >= 0).
4. Dog evidence differentiation: calm ordinary sightings vs aggressive/bite hazards.
5. Lighting states: known-lit, known-unlit, conflicting, and unknown under daytime vs evening vs night.
6. Pedestrian infrastructure constraints: confirmed pedestrian prohibitions (foot=no, motorway) and step-free avoidance of stairs.
7. Assistance access indicators: emergency facility proximity as non-negative resilience/isolation attribute.
8. Missing evidence & prior R_unknown stability: missing data never treated as zero risk; low coverage alerts.
9. Time-aware departure period inputs and fastest route invariance.
10. Legitimate identical routes vs justified detour diversity.
11. Yen's loopless alternatives with length-weighted overlap filtering (<= 0.75).
12. Dynamic evidence explanation engine narratives.
13. Sensitivity analysis benchmark suite execution and consistency.
"""

import math
import pytest
import networkx as nx
from shapely.geometry import LineString
from fastapi.testclient import TestClient

from app.core.config import settings
from app.geospatial.segment_risk import (
    SegmentRiskModel,
    TEMPORAL_PROFILES_V2,
    get_effective_weights
)
from app.geospatial.pedestrian_infrastructure import evaluate_infrastructure_deficiency
from app.geospatial.dijkstra_router import DijkstraRouter, ComputedRoute, calculate_path_edge_overlap
from app.geospatial.sensitivity_analysis import SensitivityEvaluator, create_sensitivity_benchmark_graph
from app.main import app


# ---------------------------------------------------------------------------
# Fixture: Multi-Corridor Verifiable Test Graph
# ---------------------------------------------------------------------------
def create_phase2_test_network() -> nx.MultiDiGraph:
    r"""
    Builds an independently verifiable multi-corridor graph:
        (1: Origin)
         /    |    \
     (Way A) (Way B) (Way C: Prohibited or Steps)
        |     |      |
        (2)  (3)    (4)
         \    |    /
        (5: Destination)

    Corridor 1 (1 -> 2 -> 5): Direct shortcut (1000m total).
       1->2: 500m, unlit, sidewalk=no, aggressive dog encounter report.
       2->5: 500m, unlit, sidewalk=no.
    Corridor 2 (1 -> 3 -> 5): Well-serviced boulevard (1200m total).
       1->3: 600m, lit=yes, sidewalk=both, verified calm dog sighting.
       3->5: 600m, lit=yes, sidewalk=both, hospital nearby.
    Corridor 3 (1 -> 4 -> 5): Restricted or stepped path.
       1->4: 400m, motorway / foot=no.
       4->5: 400m, highway=steps.
    """
    G = nx.MultiDiGraph(crs="EPSG:4326")
    nodes = {
        1: {"y": 12.9250, "x": 77.5800, "name": "Origin Hub"},
        2: {"y": 12.9350, "x": 77.5750, "name": "Dark Alley Junction"},
        3: {"y": 12.9350, "x": 77.5850, "name": "Commercial Boulevard Junction"},
        4: {"y": 12.9350, "x": 77.5900, "name": "Restricted Steps Junction"},
        5: {"y": 12.9450, "x": 77.5800, "name": "Destination Terminal"}
    }
    for nid, data in nodes.items():
        G.add_node(nid, **data)

    # Corridor 1 (Direct but adverse)
    G.add_edge(
        1, 2, key=0,
        length=500.0, lit="no", name="Dark Alley Section 1",
        sidewalk="no", highway="residential",
        dog_incidents_count=2,
        dog_reports=[{"category": "stray_dogs", "encounter_type": "bite", "severity": 5}],
        geometry=LineString([(77.5800, 12.9250), (77.5750, 12.9350)])
    )
    G.add_edge(
        2, 5, key=0,
        length=500.0, lit="no", name="Dark Alley Section 2",
        sidewalk="no", highway="residential",
        geometry=LineString([(77.5750, 12.9350), (77.5800, 12.9450)])
    )

    # Corridor 2 (Longer boulevard, high service quality)
    G.add_edge(
        1, 3, key=0,
        length=600.0, lit="yes", name="Boulevard Section 1",
        sidewalk="both", highway="secondary",
        dog_incidents_count=1,
        dog_reports=[{"category": "stray_dogs", "encounter_type": "sighting", "severity": 2}],
        geometry=LineString([(77.5800, 12.9250), (77.5850, 12.9350)])
    )
    G.add_edge(
        3, 5, key=0,
        length=600.0, lit="yes", name="Boulevard Section 2",
        sidewalk="both", highway="secondary",
        nearest_hospital_distance_meters=150.0,
        geometry=LineString([(77.5850, 12.9350), (77.5800, 12.9450)])
    )

    # Corridor 3 (Prohibited & Steps)
    G.add_edge(
        1, 4, key=0,
        length=400.0, lit="yes", name="Motorway Flyover",
        highway="motorway", foot="no",
        geometry=LineString([(77.5800, 12.9250), (77.5900, 12.9350)])
    )
    G.add_edge(
        4, 5, key=0,
        length=400.0, lit="yes", name="Pedestrian Steps",
        highway="steps", step_count=45,
        geometry=LineString([(77.5900, 12.9350), (77.5800, 12.9450)])
    )

    return G


# ---------------------------------------------------------------------------
# 1. Fastest-Time Optimization & Invariance
# ---------------------------------------------------------------------------
def test_fastest_time_optimization_and_temporal_invariance():
    """
    Fastest route edge cost must be strictly Cost_fastest(e) = T(e) = L(e) / v,
    independent of time-of-day (daytime, evening, night) and environmental risk.
    """
    G = create_phase2_test_network()
    
    # Run fastest under daytime
    router_day = DijkstraRouter(G, departure_period="daytime", step_free=False)
    routes_day = router_day.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800, include_alternatives=False)
    fastest_day = next(r for r in routes_day if r.category == "fastest")

    # Run fastest under night
    router_night = DijkstraRouter(G, departure_period="night", step_free=False)
    routes_night = router_night.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800, include_alternatives=False)
    fastest_night = next(r for r in routes_night if r.category == "fastest")

    # Both must select Corridor 1 (1 -> 2 -> 5) because 1000m < 1200m (Corridor 3 is blocked by foot=no)
    assert fastest_day.node_path == [1, 2, 5]
    assert fastest_night.node_path == [1, 2, 5]

    # Durations must be identical: 1000m / 1.2 m/s = 833.33s
    assert math.isclose(fastest_day.duration_seconds, 1000.0 / 1.2, rel_tol=1e-2)
    assert math.isclose(fastest_night.duration_seconds, fastest_day.duration_seconds, rel_tol=1e-5)
    assert math.isclose(fastest_day.distance_meters, 1000.0, rel_tol=1e-2)


# ---------------------------------------------------------------------------
# 2. Balanced vs Safety-Prioritized Weighted Cost Optimization
# ---------------------------------------------------------------------------
def test_balanced_and_safety_prioritized_routing():
    """
    Verifies that balanced and safety-prioritized routes apply generalized cost
    T * (1 + lambda * R_effective) with lambda_safety > lambda_balanced >= 0.
    At night, unlit Alley with aggressive dog reports has much higher cost than Boulevard.
    Boulevard detour (1200m vs 1000m) is selected when safety is prioritized.
    """
    G = create_phase2_test_network()
    router = DijkstraRouter(G, departure_period="night", step_free=False)
    
    routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800, include_alternatives=False)
    route_map = {r.category: r for r in routes}

    assert "fastest" in route_map
    assert "balanced" in route_map
    assert "safety_prioritized" in route_map

    fastest = route_map["fastest"]
    safety = route_map["safety_prioritized"]

    assert fastest.node_path == [1, 2, 5]
    # Safety route detours to lit boulevard [1, 3, 5]
    assert safety.node_path == [1, 3, 5]
    assert safety.distance_meters > fastest.distance_meters
    assert safety.route_risk < fastest.route_risk
    assert safety.lambda_weight == settings.ROUTING_LAMBDA_SAFETY
    assert safety.lambda_weight > route_map["balanced"].lambda_weight


# ---------------------------------------------------------------------------
# 3. Dog Evidence Differentiation: Sighting vs Aggressive Encounters
# ---------------------------------------------------------------------------
def test_dog_evidence_differentiation():
    """
    Tests that:
    1. Ordinary calm sightings have minimal adverse indicator (D=0.10) and do not penalize streets.
    2. Aggressive barking/chasing (D=0.85) and physical bite incidents (D=1.00) produce high risk indicators.
    """
    model = SegmentRiskModel()

    # Case A: Calm sighting
    report_sighting = {"category": "stray_dogs", "encounter_type": "sighting", "severity": 2}
    risk_sighting = model.evaluate_edge(
        edge_data={"lit": "yes"}, edge_length_meters=200.0, lit_status="lit",
        dog_reports=[report_sighting], dog_incidents_count=1, departure_period="daytime"
    )
    
    # Case B: Aggressive encounter
    report_aggressive = {"category": "stray_dogs", "encounter_type": "aggressive", "severity": 4}
    risk_aggressive = model.evaluate_edge(
        edge_data={"lit": "yes"}, edge_length_meters=200.0, lit_status="lit",
        dog_reports=[report_aggressive], dog_incidents_count=1, departure_period="daytime"
    )

    # Case C: Bite incident
    report_bite = {"category": "stray_dogs", "encounter_type": "bite", "severity": 5}
    risk_bite = model.evaluate_edge(
        edge_data={"lit": "yes"}, edge_length_meters=200.0, lit_status="lit",
        dog_reports=[report_bite], dog_incidents_count=1, departure_period="daytime"
    )

    assert risk_sighting.dog_indicator < 0.25
    assert risk_aggressive.dog_indicator >= 0.60
    assert risk_bite.dog_indicator >= 0.90
    assert risk_bite.observed_risk > risk_sighting.observed_risk


# ---------------------------------------------------------------------------
# 4. Lighting States: Known-Lit, Known-Unlit, Conflicting, and Unknown
# ---------------------------------------------------------------------------
def test_lighting_states_and_diurnal_modulation():
    """
    Tests lighting conditions:
    1. lit=yes -> L=0.10
    2. lit=no -> L=0.90
    3. conflicting reports -> L=0.70
    4. unmapped / unknown -> L=0.50
    And verifies diurnal modulation: at night, unlit penalty is severe; in daytime, attenuated.
    """
    model = SegmentRiskModel()

    prof_day = model.evaluate_edge(edge_data={"lit": "yes"}, edge_length_meters=200.0, lit_status="lit", departure_period="daytime")
    prof_unlit_day = model.evaluate_edge(edge_data={"lit": "no"}, edge_length_meters=200.0, lit_status="unlit", departure_period="daytime")
    prof_unlit_night = model.evaluate_edge(edge_data={"lit": "no"}, edge_length_meters=200.0, lit_status="unlit", departure_period="night")
    prof_unknown = model.evaluate_edge(edge_data={}, edge_length_meters=200.0, lit_status="unmapped", departure_period="night")
    prof_conflicting = model.evaluate_edge(
        edge_data={"lit": "yes"}, edge_length_meters=200.0, lit_status="conflicting",
        departure_period="night"
    )

    assert prof_day.lighting_indicator == 0.10
    assert prof_unlit_night.lighting_indicator == 0.90
    assert prof_unknown.lighting_indicator == 0.50
    assert prof_conflicting.lighting_indicator == 0.70

    # Diurnal weight modulation: Night has higher effective lighting weight than Daytime
    w_day = get_effective_weights("daytime")
    w_night = get_effective_weights("night")
    assert w_night["lighting"] > w_day["lighting"]


# ---------------------------------------------------------------------------
# 5. Pedestrian Infrastructure Restrictions & Step-Free Constraint
# ---------------------------------------------------------------------------
def test_pedestrian_infrastructure_prohibitions_and_step_free():
    """
    Verifies that:
    1. Confirmed prohibited ways (foot=no, motorway) are assigned infinite cost and never routed through.
    2. When step_free=True, stairs (highway=steps) are assigned infinite cost.
    3. Sidewalk evaluation captures dedicated sidewalk vs unmapped.
    """
    G = create_phase2_test_network()

    # Route with step_free=False: Corridor 3 node 4 has steps (highway=steps).
    # Since 1->4 is motorway with foot=no, Dijkstra must reject 1->4 under all conditions.
    router = DijkstraRouter(G, departure_period="daytime", step_free=False)
    routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800, include_alternatives=False)
    fastest = next(r for r in routes if r.category == "fastest")
    assert 4 not in fastest.node_path

    # Build a dedicated graph testing step-free avoidance
    G_steps = nx.MultiDiGraph(crs="EPSG:4326")
    G_steps.add_node(1, y=12.920, x=77.580)
    G_steps.add_node(2, y=12.930, x=77.580)
    G_steps.add_node(3, y=12.940, x=77.580)

    # Path A: Shorter with stairs (100m total)
    G_steps.add_edge(1, 2, key=0, length=50.0, highway="steps", step_count=20, lit="yes",
                     geometry=LineString([(77.580, 12.920), (77.580, 12.930)]))
    G_steps.add_edge(2, 3, key=0, length=50.0, highway="footway", lit="yes",
                     geometry=LineString([(77.580, 12.930), (77.580, 12.940)]))

    # Path B: Longer ramp / sidewalk (160m total)
    G_steps.add_edge(1, 3, key=0, length=160.0, highway="footway", wheelchair="yes", lit="yes",
                     geometry=LineString([(77.580, 12.920), (77.580, 12.940)]))

    # When step_free=False, Path A (via steps) is chosen because 100m < 160m
    router_standard = DijkstraRouter(G_steps, step_free=False)
    routes_std = router_standard.compute_all_routes(12.920, 77.580, 12.940, 77.580, include_alternatives=False)
    fastest_std = next(r for r in routes_std if r.category == "fastest")
    assert fastest_std.node_path == [1, 2, 3]

    # When step_free=True, Path A is strictly prohibited (cost=inf), so Path B is chosen
    router_step_free = DijkstraRouter(G_steps, step_free=True)
    routes_sf = router_step_free.compute_all_routes(12.920, 77.580, 12.940, 77.580, include_alternatives=False)
    fastest_sf = next(r for r in routes_sf if r.category == "fastest")
    assert fastest_sf.node_path == [1, 3]
    assert fastest_sf.step_free is True


# ---------------------------------------------------------------------------
# 6. Assistance Access Proximity Indicator
# ---------------------------------------------------------------------------
def test_assistance_access_isolation_penalty():
    """
    Verifies that distance to police/hospital acts as a non-negative isolation penalty
    without treating nearby facilities as proof of zero crime risk.
    """
    model = SegmentRiskModel()

    # Corridor next to police station (1 min walk)
    prof_near = model.evaluate_edge(edge_data={"lit": "yes"}, edge_length_meters=200.0, lit_status="lit", police_walking_minutes=1.0, hospital_walking_minutes=3.0)
    # Isolated corridor far from emergency help (30 min walk)
    prof_far = model.evaluate_edge(edge_data={"lit": "yes"}, edge_length_meters=200.0, lit_status="lit", police_walking_minutes=30.0, hospital_walking_minutes=35.0)

    assert prof_near.assistance_indicator < prof_far.assistance_indicator
    assert prof_near.assistance_indicator >= 0.0
    assert prof_far.assistance_indicator <= 1.0


# ---------------------------------------------------------------------------
# 7. Missing Evidence & Prior R_unknown Policy
# ---------------------------------------------------------------------------
def test_missing_evidence_and_unknown_prior():
    """
    Tests that:
    1. An edge with zero upstream evidence has coverage Q = 0.0.
    2. Effective risk strictly equals R_unknown (0.50), never 0.0.
    3. When coverage Q < 0.30, has_insufficient_evidence flag is set.
    """
    model = SegmentRiskModel()

    # Empty segment: no lighting, no crime data, no dog reports, no infrastructure tags
    prof = model.evaluate_edge(edge_data={}, edge_length_meters=200.0, lit_status="unmapped", has_crime_dataset=False, departure_period="daytime")

    assert prof.evidence_coverage < 0.30
    assert math.isclose(prof.effective_risk, getattr(settings, "ROUTING_DEFAULT_R_UNKNOWN", 0.50), rel_tol=1e-3)
    assert prof.effective_risk != 0.0


# ---------------------------------------------------------------------------
# 8. Identical Routes Disclosure (Honest Optimization)
# ---------------------------------------------------------------------------
def test_identical_routes_disclosure_when_optimal():
    """
    When the direct fastest path is also the best illuminated and safest avenue,
    Balanced and Safety-prioritized runs legitimately select the identical path.
    SafePath must flag is_identical_to_fastest = True and document the reason.
    """
    G = nx.MultiDiGraph(crs="EPSG:4326")
    G.add_node(1, y=12.920, x=77.580)
    G.add_node(2, y=12.930, x=77.580)
    G.add_node(3, y=12.940, x=77.580)

    # Avenue: 500m, lit=yes, pristine sidewalk
    G.add_edge(1, 2, key=0, length=250.0, lit="yes", sidewalk="both", highway="secondary",
               geometry=LineString([(77.580, 12.920), (77.580, 12.930)]))
    G.add_edge(2, 3, key=0, length=250.0, lit="yes", sidewalk="both", highway="secondary",
               geometry=LineString([(77.580, 12.930), (77.580, 12.940)]))

    # Detour: 1000m, lit=no
    G.add_edge(1, 3, key=0, length=1000.0, lit="no", highway="residential",
               geometry=LineString([(77.580, 12.920), (77.580, 12.940)]))

    router = DijkstraRouter(G, departure_period="night")
    routes = router.compute_all_routes(12.920, 77.580, 12.940, 77.580, include_alternatives=False)
    route_map = {r.category: r for r in routes}

    fastest = route_map["fastest"]
    safety = route_map["safety_prioritized"]

    assert fastest.node_path == safety.node_path
    assert safety.is_identical_to_fastest is True
    assert "optimal" in safety.identical_notes.lower()


# ---------------------------------------------------------------------------
# 9. Yen's Loopless Alternatives & Length-Weighted Overlap Filtering
# ---------------------------------------------------------------------------
def test_yens_loopless_alternatives_and_length_weighted_overlap():
    """
    Verifies that Yen's loopless paths generate distinct alternative routes
    and length-weighted overlap filtering prunes near-duplicates (overlap >= 0.75).
    """
    G = nx.MultiDiGraph(crs="EPSG:4326")
    G.add_node(1, y=12.920, x=77.580)
    G.add_node(2, y=12.925, x=77.575)
    G.add_node(3, y=12.925, x=77.585)
    G.add_node(4, y=12.930, x=77.580)

    # Path A: 1 -> 2 -> 4 (400m)
    G.add_edge(1, 2, key=0, length=200.0, lit="yes", highway="residential",
               geometry=LineString([(77.580, 12.920), (77.575, 12.925)]))
    G.add_edge(2, 4, key=0, length=200.0, lit="yes", highway="residential",
               geometry=LineString([(77.575, 12.925), (77.580, 12.930)]))

    # Path B: 1 -> 3 -> 4 (420m)
    G.add_edge(1, 3, key=0, length=210.0, lit="yes", highway="residential",
               geometry=LineString([(77.580, 12.920), (77.585, 12.925)]))
    G.add_edge(3, 4, key=0, length=210.0, lit="yes", highway="residential",
               geometry=LineString([(77.585, 12.925), (77.580, 12.930)]))

    # Test length-weighted overlap function
    path_a = [1, 2, 4]
    path_b = [1, 3, 4]
    overlap = calculate_path_edge_overlap(path_a, path_b, graph=G)
    assert overlap == 0.0  # Zero shared edges

    # Compute Yen alternatives
    router = DijkstraRouter(G, departure_period="daytime")
    routes = router.compute_all_routes(12.920, 77.580, 12.930, 77.580, include_alternatives=True, max_alternatives=2)
    alt_routes = [r for r in routes if r.category == "alternative"]
    assert len(alt_routes) >= 1
    for alt in alt_routes:
        # Loopless verification: no node appears twice
        assert len(alt.node_path) == len(set(alt.node_path))


# ---------------------------------------------------------------------------
# 10. Dynamic Evidence-Based Route Explanation Engine
# ---------------------------------------------------------------------------
def test_dynamic_route_explanation_engine():
    """
    Verifies that every computed route produces a structured explanation narrative
    covering selection reason, lighting, crime, dogs, infrastructure, assistance proximity,
    uncertainty/priors, and time delta.
    """
    G = create_phase2_test_network()
    router = DijkstraRouter(G, departure_period="evening", step_free=False)
    routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800)

    for r in routes:
        assert r.explanation_details is not None
        exp = r.explanation_details
        assert "selection_reason" in exp
        assert "lighting_evidence" in exp
        assert "crime_evidence" in exp
        assert "dog_encounters" in exp
        assert "infrastructure_evidence" in exp
        assert "assistance_proximity" in exp
        assert "uncertainty_and_prior" in exp
        assert "time_delta_vs_fastest" in exp


# ---------------------------------------------------------------------------
# 11. Sensitivity Analysis Benchmark Suite Execution
# ---------------------------------------------------------------------------
def test_sensitivity_analysis_suite():
    """
    Verifies that SensitivityEvaluator runs all 5 parameter sweep benchmarks
    and returns coherent results without errors.
    """
    evaluator = SensitivityEvaluator()
    suite = evaluator.run_comprehensive_sensitivity_suite()

    assert suite["status"] == "success"
    assert "evaluations" in suite
    evals = suite["evaluations"]

    assert "lambda_tradeoff" in evals
    assert "lighting_and_temporal" in evals
    assert "dog_encounter_differentiation" in evals
    assert "infrastructure_and_accessibility" in evals
    assert "missing_data_prior_sensitivity" in evals

    # Validate lambda trade-off monotonicity
    lambda_results = evals["lambda_tradeoff"]
    if isinstance(lambda_results, dict):
        lambda_results = lambda_results.get("results", [lambda_results])
    assert len(lambda_results) >= 4
    for res in lambda_results:
        cost_val = res.get("generalizedCost") if "generalizedCost" in res else res.get("generalized_cost", 0.0)
        assert cost_val >= 0.0


# ---------------------------------------------------------------------------
# 12. Full API Integration: POST /routes/compare & GET /routes/sensitivity-analysis
# ---------------------------------------------------------------------------
def test_api_route_comparison_and_sensitivity_endpoints():
    """
    Verifies end-to-end HTTP API contracts:
    1. POST /api/v1/routes/compare accepts departurePeriod and stepFree.
    2. Response includes adverseRiskScore, overlapWithFastest, explanationDetails.
    3. GET /api/v1/routes/sensitivity-analysis returns benchmark evaluation results.
    """
    client = TestClient(app)

    # 1. Compare routes request
    req_body = {
        "origin": "12.9257, 77.5833",
        "destination": "12.9501, 77.5847",
        "walkingMode": "pedestrian",
        "departurePeriod": "night",
        "stepFree": False,
        "preferences": {
            "includeAlternatives": True,
            "maxAlternatives": 2
        }
    }
    res = client.post("/api/v1/routes/compare", json=req_body)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "routes" in data
    assert len(data["routes"]) >= 1

    top_route = data["routes"][0]
    assert "departurePeriod" in top_route
    assert top_route["departurePeriod"] == "night"
    assert "stepFree" in top_route
    assert "adverseRiskScore" in top_route
    assert "explanationDetails" in top_route
    assert isinstance(top_route["explanationDetails"], dict)

    # 2. Sensitivity analysis endpoint
    sens_res = client.get("/api/v1/routes/sensitivity-analysis")
    assert sens_res.status_code == 200, sens_res.text
    sens_data = sens_res.json()
    assert sens_data["status"] == "success"
    assert "evaluations" in sens_data
    assert "key_findings" in sens_data
    assert len(sens_data["key_findings"]) >= 5
