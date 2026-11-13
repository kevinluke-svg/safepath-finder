import sys
import os
import time
import math
import json
import statistics
import networkx as nx
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath('backend'))

from app.core.config import settings
from app.geospatial.study_area import StudyArea
from app.geospatial.network_builder import build_bengaluru_pilot_network
from app.geospatial.dijkstra_router import DijkstraRouter
from app.geospatial.facilities_adapter import OsmFacilityAdapter
from app.geospatial.facility_router import FacilityRouter
from app.geospatial.crime_adapter import CsvCrimeAdapter
from app.services.geocoding_service import GeocodingService
# 
from app.db.session import SessionLocal

def measure_benchmarks():
    print("=== EMPIRICAL PERFORMANCE BENCHMARKING ===")
    study_area = StudyArea.from_settings()

    # 1. Location search / geocoding response time (Cold & Warm)
    geo = GeocodingService(study_area=study_area)
    times_geo_cold = []
    t0 = time.perf_counter()
    res1 = geo.search("Jayanagar 4th Block")
    t_cold = (time.perf_counter() - t0) * 1000
    times_geo_cold.append(t_cold)

    times_geo_warm = []
    for _ in range(20):
        t0 = time.perf_counter()
        _ = geo.search("Jayanagar 4th Block")
        times_geo_warm.append((time.perf_counter() - t0) * 1000)

    print(f"Location Search (Cold): {t_cold:.3f} ms")
    print(f"Location Search (Warm, 20 runs): Mean={statistics.mean(times_geo_warm):.3f} ms, Median={statistics.median(times_geo_warm):.3f} ms, Min={min(times_geo_warm):.3f} ms")

    # 2. Graph loading time (Cold & Warm)
    graph_path = "backend/data/cache/pedestrian_bengaluru_pilot_corridor_12p9200_77p5700_12p9850_77p6200.graphml"
    t0 = time.perf_counter()
    _ = nx.read_graphml(graph_path)
    t_graph_cold = (time.perf_counter() - t0) * 1000

    times_graph_warm = []
    for _ in range(20):
        t0 = time.perf_counter()
        g = build_bengaluru_pilot_network()
        times_graph_warm.append((time.perf_counter() - t0) * 1000)

    print(f"Pedestrian Graph Load (Cold from GraphML file): {t_graph_cold:.2f} ms")
    print(f"Pedestrian Graph Load (Warm cached, 20 runs): Mean={statistics.mean(times_graph_warm):.4f} ms, Median={statistics.median(times_graph_warm):.4f} ms")

    # 3. Facility and Crime Evidence aggregation
    t0 = time.perf_counter()
    fac_res = OsmFacilityAdapter().get_facilities(study_area)
    t_fac = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    crime_res = CsvCrimeAdapter().load_crime_dataset()
    t_crime = (time.perf_counter() - t0) * 1000

    print(f"Nearby Facilities Retrieval (34 POIs): {t_fac:.3f} ms")
    print(f"Crime Evidence Loading & Indexing: {t_crime:.3f} ms")

    # 4. Dijkstra Router Initialization & Snapping
    router = DijkstraRouter(g, facilities_result=fac_res, crime_dataset=crime_res)
    
    # Measure Coordinate snapping time via router._find_nearest_node (uses STRtree)
    times_snap = []
    test_coords = [
        (12.9257, 77.5833), (12.9463, 77.5802), (12.9360, 77.5750),
        (12.9760, 77.5920), (12.9500, 77.5850)
    ]
    for lat, lon in test_coords:
        t0 = time.perf_counter()
        node_id, snap_dist = router._find_nearest_node(lat, lon)
        times_snap.append((time.perf_counter() - t0) * 1000)

    print(f"Coordinate Snapping (STRtree, 5 test coords): Mean={statistics.mean(times_snap):.4f} ms, Median={statistics.median(times_snap):.4f} ms")

    # 5. Dijkstra Execution Isolated (single preference)
    orig = (12.9257, 77.5833)
    dest = (12.9463, 77.5802)
    times_dijkstra = []
    for _ in range(10):
        t0 = time.perf_counter()
        routes_single = router.compute_all_routes(orig[0], orig[1], dest[0], dest[1], ranking_preference="safety", include_alternatives=False, departure_period="evening")
        times_dijkstra.append((time.perf_counter() - t0) * 1000)

    print(f"Dijkstra Execution (Fastest + Balanced + Safety without alts, 10 runs): Mean={statistics.mean(times_dijkstra):.2f} ms, Median={statistics.median(times_dijkstra):.2f} ms")

    # 6. Full Route Comparison (all 3 preferences + 3 Yen's alternatives)
    times_comparison = []
    for _ in range(10):
        t0 = time.perf_counter()
        routes = router.compute_all_routes(orig[0], orig[1], dest[0], dest[1], ranking_preference="safety", include_alternatives=True, departure_period="evening")
        times_comparison.append((time.perf_counter() - t0) * 1000)

    print(f"Full Route Comparison (3 Primary + 3 Yen's Alternatives, 10 runs):")
    print(f"  Mean: {statistics.mean(times_comparison):.2f} ms")
    print(f"  Median: {statistics.median(times_comparison):.2f} ms")
    print(f"  Min: {min(times_comparison):.2f} ms")
    print(f"  Max: {max(times_comparison):.2f} ms")

    # 7. Isolated Yen's Alternative Generation
    times_yens = []
    for _ in range(10):
        t0 = time.perf_counter()
        routes_no_alt = router.compute_all_routes(orig[0], orig[1], dest[0], dest[1], ranking_preference="safety", include_alternatives=False, departure_period="evening")
        t_base = time.perf_counter() - t0
        
        t0 = time.perf_counter()
        routes_with_alt = router.compute_all_routes(orig[0], orig[1], dest[0], dest[1], ranking_preference="safety", include_alternatives=True, departure_period="evening")
        t_with = time.perf_counter() - t0
        times_yens.append((t_with - t_base) * 1000)

    print(f"Isolated Yen's K-Shortest Paths (k=3 loopless paths): Mean={statistics.mean(times_yens):.2f} ms, Median={statistics.median(times_yens):.2f} ms")

    # 8. End-to-End API endpoint call (via TestClient)
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    payload = {
        "origin": "Jayanagar 4th Block, Bengaluru",
        "destination": "Lalbagh West Gate, Bengaluru",
        "walkingMode": "pedestrian",
        "departurePeriod": "evening",
        "preferences": {
            "includeAlternatives": True,
            "maxAlternatives": 3,
            "avoidPoorLighting": True
        }
    }
    
    t0 = time.perf_counter()
    resp_cold = client.post("/api/v1/routes/compare", json=payload)
    t_api_cold = (time.perf_counter() - t0) * 1000
    assert resp_cold.status_code == 200, f"API error: {resp_cold.text}"

    times_api_warm = []
    for _ in range(10):
        t0 = time.perf_counter()
        resp = client.post("/api/v1/routes/compare", json=payload)
        times_api_warm.append((time.perf_counter() - t0) * 1000)
        assert resp.status_code == 200

    print(f"End-to-End API /routes/compare (Cold): {t_api_cold:.2f} ms")
    print(f"End-to-End API /routes/compare (Warm, 10 runs): Mean={statistics.mean(times_api_warm):.2f} ms, Median={statistics.median(times_api_warm):.2f} ms, Min={min(times_api_warm):.2f} ms")

    # 9. Frontend initial load measurements
    import urllib.request
    t0 = time.perf_counter()
    req = urllib.request.urlopen("http://127.0.0.1:8000/safepath_pro.html")
    content = req.read()
    t_fe_load = (time.perf_counter() - t0) * 1000
    print(f"Frontend Initial HTML Load (http://127.0.0.1:8000/safepath_pro.html): {t_fe_load:.2f} ms (Size: {len(content)/1024:.1f} KB)")

    print("\n=== PERFORMANCE BENCHMARKS COMPLETE ===")

if __name__ == '__main__':
    measure_benchmarks()
