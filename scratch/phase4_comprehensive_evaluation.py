import sys
import os
import time
import math
import json
import logging
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath('backend'))

from app.core.config import settings
from app.geospatial.study_area import StudyArea
from app.geospatial.network_builder import build_bengaluru_pilot_network
from app.geospatial.dijkstra_router import DijkstraRouter, ComputedRoute, calculate_path_edge_overlap
from app.geospatial.segment_risk import SegmentRiskModel, SegmentRiskProfile
from app.geospatial.facilities_adapter import OsmFacilityAdapter
from app.geospatial.facility_router import FacilityRouter
from app.geospatial.crime_adapter import CsvCrimeAdapter
from app.geospatial.pedestrian_infrastructure import compute_route_infrastructure_summary
from app.geospatial.sensitivity_analysis import SensitivityEvaluator
from app.services.geocoding_service import GeocodingService
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.encryption import encrypt_field, decrypt_field, mask_phone_number

logging.basicConfig(level=logging.ERROR)

def run_tests():
    print("=== PHASE 4 COMPREHENSIVE EVALUATION STARTED ===")
    results = {}

    # 1. Routing & Algorithm Validation
    print("\n--- 1. ROUTING ALGORITHM & MATHEMATICAL VALIDATION ---")
    study_area = StudyArea.from_settings()
    t0 = time.perf_counter()
    graph = build_bengaluru_pilot_network()
    t_graph = time.perf_counter() - t0
    print(f"Graph loaded in {t_graph:.3f}s. Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

    fac_adapter = OsmFacilityAdapter()
    fac_res = fac_adapter.get_facilities(study_area)
    crime_adapter = CsvCrimeAdapter()
    crime_res = crime_adapter.load_crime_dataset()

    router = DijkstraRouter(graph, facilities_result=fac_res, crime_dataset=crime_res)

    # Test OD Pair: Jayanagar 4th Block -> Lalbagh West Gate
    orig = (12.9257, 77.5833)
    dest = (12.9463, 77.5802)

    t0 = time.perf_counter()
    fastest = router.find_optimal_route(orig, dest, preference="fastest", departure_period="evening")
    t_fastest = time.perf_counter() - t0

    t0 = time.perf_counter()
    balanced = router.find_optimal_route(orig, dest, preference="balanced", departure_period="evening")
    t_balanced = time.perf_counter() - t0

    t0 = time.perf_counter()
    safety = router.find_optimal_route(orig, dest, preference="safety", departure_period="evening")
    t_safety = time.perf_counter() - t0

    print(f"Fastest route: dist={fastest.total_distance:.1f}m, time={fastest.total_time/60:.2f}min, cost={fastest.total_generalized_cost:.2f}, risk={fastest.risk_indicator:.3f}, calc_time={t_fastest*1000:.2f}ms")
    print(f"Balanced route: dist={balanced.total_distance:.1f}m, time={balanced.total_time/60:.2f}min, cost={balanced.total_generalized_cost:.2f}, risk={balanced.risk_indicator:.3f}, calc_time={t_balanced*1000:.2f}ms")
    print(f"Safety route: dist={safety.total_distance:.1f}m, time={safety.total_time/60:.2f}min, cost={safety.total_generalized_cost:.2f}, risk={safety.risk_indicator:.3f}, calc_time={t_safety*1000:.2f}ms")

    # Verify Yen's K-shortest paths
    t0 = time.perf_counter()
    alts = router.find_alternative_routes(orig, dest, k=3, preference="safety", departure_period="evening")
    t_yens = time.perf_counter() - t0
    print(f"Yen's K-shortest paths ({len(alts)} found) in {t_yens*1000:.2f}ms:")
    for idx, alt in enumerate(alts):
        overlap = calculate_path_edge_overlap(graph, safety.nodes, alt.nodes)
        has_loops = len(alt.nodes) != len(set(alt.nodes))
        print(f"  Alt {idx+1}: dist={alt.total_distance:.1f}m, cost={alt.total_generalized_cost:.2f}, overlap_with_primary={overlap*100:.1f}%, loops={has_loops}")
        assert not has_loops, f"Loop detected in alternative {idx+1}!"

    # Test ETA calculation consistency: T = Distance / 1.2 m/s
    expected_duration_min = fastest.total_distance / 1.2 / 60
    actual_duration_min = fastest.total_time / 60
    print(f"\n--- 2. WALKING TIME & SPEED CONSISTENCY ---")
    print(f"Distance: {fastest.total_distance:.2f} m ({fastest.total_distance/1000:.3f} km)")
    print(f"Backend walking speed: {fastest.walking_speed_mps} m/s ({fastest.walking_speed_kmh} km/h)")
    print(f"Theoretical time at 1.2 m/s: {expected_duration_min:.2f} min")
    print(f"Actual model duration: {actual_duration_min:.2f} min (Diff: {abs(actual_duration_min - expected_duration_min):.4f} min)")
    assert abs(actual_duration_min - expected_duration_min) < 0.1, "ETA calculation mismatch!"

    # Test Infrastructure 3-state calculation
    infra_sum = compute_route_infrastructure_summary(graph, fastest.nodes)
    print(f"\n--- 3. PEDESTRIAN INFRASTRUCTURE (3-STATE) ---")
    print(f"Sidewalk known: {infra_sum.known_sidewalk_distance_meters:.1f}m ({infra_sum.known_sidewalk_percentage:.1f}%)")
    print(f"Sidewalk unmapped: {infra_sum.unmapped_sidewalk_distance_meters:.1f}m ({infra_sum.unmapped_sidewalk_percentage:.1f}%)")
    print(f"Sidewalk absent: {infra_sum.absent_sidewalk_distance_meters:.1f}m ({infra_sum.absent_sidewalk_percentage:.1f}%)")
    print(f"Total traversed: {infra_sum.total_traversed_distance_meters:.1f}m")
    sum_pct = infra_sum.known_sidewalk_percentage + infra_sum.unmapped_sidewalk_percentage + infra_sum.absent_sidewalk_percentage
    print(f"Total percentage: {sum_pct:.2f}% (Expect 100.0%)")
    assert abs(sum_pct - 100.0) < 0.1, "Infrastructure percentages must sum to 100%!"

    # Test Streetlight calculation
    light_sum = fastest.streetlight_summary
    print(f"\n--- 4. STREETLIGHT AUDIT ---")
    print(f"Lit: {light_sum['litDistanceMeters']:.1f}m ({light_sum['litPercentage']:.1f}%)")
    print(f"Unlit: {light_sum['unlitDistanceMeters']:.1f}m ({light_sum['unlitPercentage']:.1f}%)")
    print(f"Unmapped: {light_sum['unmappedDistanceMeters']:.1f}m ({light_sum['unmappedPercentage']:.1f}%)")
    light_sum_pct = light_sum['litPercentage'] + light_sum['unlitPercentage'] + light_sum['unmappedPercentage']
    print(f"Total percentage: {light_sum_pct:.2f}% (Expect 100.0%)")
    assert abs(light_sum_pct - 100.0) < 0.1, "Streetlight percentages must sum to 100%!"

    # Test Facility Adapter Bounds & Distances
    print(f"\n--- 5. FACILITIES BOUNDS & NETWORK DISTANCE ---")
    fac_router = FacilityRouter(graph, fac_res.all_facilities)
    fac_matches = fac_router.find_facilities_along_route(fastest.nodes, corridor_buffer_meters=350)
    print(f"Total mapped POIs in database: {len(fac_res.all_facilities)}")
    for f in fac_res.all_facilities:
        assert 12.8 <= f.latitude <= 13.15 and 77.4 <= f.longitude <= 77.8, f"Facility {f.name} coordinates invalid: {f.latitude}, {f.longitude}"
    print(f"All {len(fac_res.all_facilities)} facilities verified within Greater Bengaluru bounds.")
    print(f"Facilities along Jayanagar -> Lalbagh corridor: {len(fac_matches)}")
    for fm in fac_matches[:3]:
        print(f"  {fm.name} ({fm.category}): straight_line={fm.straight_line_distance_meters:.1f}m, network={fm.network_distance_meters:.1f}m, access={fm.access_point_type}")
        assert fm.network_distance_meters >= fm.straight_line_distance_meters - 1.0, "Network distance cannot be shorter than Euclidean distance!"

    # Test Geocoding Service (case-insensitivity, partial matching, coordinates)
    print(f"\n--- 6. GEOCODING & LOCATION SEARCH ---")
    geo = GeocodingService(study_area=study_area)
    res_lower = geo.geocode("jayanagar 4th block")
    res_upper = geo.geocode("JAYANAGAR 4TH BLOCK")
    res_partial = geo.geocode("lalbagh")
    print(f"Query 'jayanagar 4th block': found {len(res_lower)} results. First: {res_lower[0].display_name}")
    print(f"Query 'JAYANAGAR 4TH BLOCK': found {len(res_upper)} results. First: {res_upper[0].display_name}")
    print(f"Query 'lalbagh': found {len(res_partial)} results. First: {res_partial[0].display_name}")
    assert len(res_lower) > 0 and len(res_upper) > 0, "Geocoding failed on case sensitivity!"
    assert res_lower[0].latitude == res_upper[0].latitude, "Coordinates mismatch for case difference!"

    # Test Coordinates Parsing
    coord_res = geo.geocode("12.9257, 77.5833")
    print(f"Coordinate input '12.9257, 77.5833': parsed as {coord_res[0].latitude}, {coord_res[0].longitude}")
    assert abs(coord_res[0].latitude - 12.9257) < 0.0001, "Coordinate parsing failed!"

    # Test Off-network / out of bounds
    oob_res = geo.geocode("99.9999, 99.9999")
    print(f"Out of bounds query '99.9999, 99.9999': returns {len(oob_res)} results (is_within_study_area={oob_res[0].is_within_study_area if oob_res else None})")
    assert len(oob_res) == 0 or not oob_res[0].is_within_study_area, "Out of bounds should be marked unsupported!"

    # Test Security: Encryption & Privacy
    print(f"\n--- 7. SECURITY & PRIVACY VALIDATION ---")
    test_phone = "+91 98765 43210"
    enc = encrypt_field(test_phone)
    dec = decrypt_field(enc)
    masked = mask_phone_number(test_phone)
    print(f"Plain phone: {test_phone}")
    print(f"Encrypted token (Fernet): {enc[:30]}...")
    print(f"Decrypted: {dec}")
    print(f"Masked phone: {masked}")
    assert dec == test_phone, "Decryption mismatch!"
    assert "43210" in masked and "98765" not in masked, "Phone masking failed!"

    # Test Password Hashing
    pw = "ResearchPass123!"
    pw_hash = get_password_hash(pw)
    assert verify_password(pw, pw_hash), "Password verification failed!"
    assert not verify_password("WrongPass", pw_hash), "Password false positive!"
    print(f"Password hashing verified with bcrypt.")

    # Test Sensitivity Analysis Suite
    print(f"\n--- 8. SENSITIVITY ANALYSIS SUITE ---")
    sens_eval = SensitivityEvaluator()
    suite = sens_eval.run_comprehensive_sensitivity_suite()
    print(f"Ran sensitivity suite with {len(suite)} benchmark categories:")
    for k, v in suite.items():
        if isinstance(v, dict) and 'evaluations' in v:
            print(f"  Category {k}: {len(v['evaluations'])} evaluations")
        else:
            print(f"  Category {k}: {list(v.keys()) if isinstance(v, dict) else v}")

    print("\n=== ALL EVALUATION CHECKS PASSED ===")

if __name__ == '__main__':
    run_tests()
