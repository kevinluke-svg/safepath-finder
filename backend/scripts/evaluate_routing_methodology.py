"""
SafePath Finder — Research Methodology & Routing Engine Evaluation Script
Executes multi-scenario route comparisons and sensitivity analyses:
1. Baseline Fastest vs Balanced vs Safety-prioritized on multiple corridor OD pairs.
2. Metrics measurement: travel time, detour ratio, risk index, evidence coverage, lighting %, facilities proximity.
3. Sensitivity analysis over lambda (risk weight) and R_unknown (missing-data prior).
4. Exports structured results for academic documentation and research transparency.
"""

import os
import json
import logging
from typing import Dict, Any, List

from app.geospatial.study_area import StudyArea
from app.geospatial.segment_risk import SegmentRiskModel
from app.geospatial.dijkstra_router import DijkstraRouter
from app.geospatial.network_builder import build_bengaluru_pilot_network
from app.geospatial.facilities_adapter import OsmFacilityAdapter
from app.geospatial.crime_adapter import CsvCrimeAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_evaluation() -> Dict[str, Any]:
    study_area = StudyArea.from_settings()
    graph = build_bengaluru_pilot_network()

    # Load facilities and crime datasets
    fac_adapter = OsmFacilityAdapter()
    fac_res = fac_adapter.get_facilities(study_area)
    crime_adapter = CsvCrimeAdapter()
    crime_res = crime_adapter.load_crime_dataset()

    scenarios = [
        {
            "id": "scenario-1",
            "name": "Jayanagar 4th Block → Lalbagh West Gate",
            "origin": (12.9257, 77.5833),
            "dest": (12.9460, 77.5844),
            "context": "South suburban commercial hub to botanical perimeter lane"
        },
        {
            "id": "scenario-2",
            "name": "South End Circle → Gandhi Bazaar",
            "origin": (12.9370, 77.5835),
            "dest": (12.9420, 77.5720),
            "context": "Metro transit hub to traditional shopping high-street"
        },
        {
            "id": "scenario-3",
            "name": "Cubbon Park → MG Road",
            "origin": (12.9770, 77.5920),
            "dest": (12.9750, 77.6050),
            "context": "Central civic parkway to commercial promenade"
        },
        {
            "id": "scenario-4",
            "name": "Jayanagar 4th Block → MG Road",
            "origin": (12.9257, 77.5833),
            "dest": (12.9750, 77.6050),
            "context": "Long-distance multi-corridor transit axis (South to Central)"
        }
    ]

    scenario_results = []

    for sc in scenarios:
        risk_model = SegmentRiskModel(
            walking_speed_mps=1.2,
            lambda_balanced=1.0,
            lambda_safety=3.0,
            r_unknown_prior=0.50
        )
        router = DijkstraRouter(
            graph=graph,
            risk_model=risk_model,
            facilities_result=fac_res,
            crime_dataset=crime_res,
            max_detour_ratio=1.40,
            overlap_threshold=0.80,
            max_alternatives=2
        )

        routes = router.compute_all_routes(
            origin_lat=sc["origin"][0],
            origin_lon=sc["origin"][1],
            dest_lat=sc["dest"][0],
            dest_lon=sc["dest"][1],
            include_alternatives=True
        )

        fastest_r = next(r for r in routes if r.category == "fastest")
        fastest_time = fastest_r.duration_seconds

        routes_data = []
        for r in routes:
            time_diff_s = r.duration_seconds - fastest_time
            time_diff_min = round(time_diff_s / 60.0, 1)
            pct_diff = round((time_diff_s / fastest_time) * 100.0, 1) if fastest_time > 0 else 0.0

            routes_data.append({
                "id": r.id,
                "name": r.name,
                "category": r.category,
                "preference": r.preference,
                "distanceMeters": r.distance_meters,
                "durationSeconds": r.duration_seconds,
                "durationMinutes": round(r.duration_seconds / 60.0, 1),
                "detourMinutes": time_diff_min,
                "detourPercentage": pct_diff,
                "routeRiskIndicator": r.route_risk_indicator,
                "evidenceCoverage": r.evidence_coverage,
                "evidenceCoveragePercentage": int(round(r.evidence_coverage * 100)),
                "litPercentage": r.lit_percentage,
                "unlitPercentage": r.unlit_percentage,
                "unmappedPercentage": r.unmapped_percentage,
                "policeDistanceMeters": r.min_police_distance_meters,
                "hospitalDistanceMeters": r.min_hospital_distance_meters,
                "isIdenticalToFastest": r.is_identical_to_fastest,
                "identicalNotes": r.identical_notes,
                "nodePath": r.node_path,
                "tradeoffs": r.tradeoffs
            })

        scenario_results.append({
            "scenario": sc,
            "routes": routes_data
        })

    # -------------------------------------------------------------------------
    # SENSITIVITY ANALYSIS 1: Varying Risk Weight Lambda
    # -------------------------------------------------------------------------
    sc1 = scenarios[0]
    lambda_values = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
    lambda_sensitivity = []

    for l_val in lambda_values:
        rm = SegmentRiskModel(lambda_safety=l_val, r_unknown_prior=0.50)
        rt = DijkstraRouter(graph, rm)
        computed = rt.compute_all_routes(
            sc1["origin"][0], sc1["origin"][1],
            sc1["dest"][0], sc1["dest"][1],
            ranking_preference="safety",
            include_alternatives=False
        )
        best_r = computed[0]
        lambda_sensitivity.append({
            "lambda": l_val,
            "selectedPath": best_r.node_path,
            "durationMinutes": round(best_r.duration_seconds / 60.0, 1),
            "distanceMeters": best_r.distance_meters,
            "litPercentage": best_r.lit_percentage,
            "routeRisk": best_r.route_risk_indicator,
            "totalCost": round(best_r.total_cost, 2)
        })

    # -------------------------------------------------------------------------
    # SENSITIVITY ANALYSIS 2: Varying Unknown Prior R_unknown
    # -------------------------------------------------------------------------
    prior_values = [0.20, 0.40, 0.50, 0.60, 0.80]
    prior_sensitivity = []

    for p_val in prior_values:
        rm = SegmentRiskModel(lambda_safety=3.0, r_unknown_prior=p_val)
        rt = DijkstraRouter(graph, rm)
        computed = rt.compute_all_routes(
            sc1["origin"][0], sc1["origin"][1],
            sc1["dest"][0], sc1["dest"][1],
            ranking_preference="safety",
            include_alternatives=False
        )
        best_r = computed[0]
        prior_sensitivity.append({
            "rUnknownPrior": p_val,
            "selectedPath": best_r.node_path,
            "durationMinutes": round(best_r.duration_seconds / 60.0, 1),
            "distanceMeters": best_r.distance_meters,
            "routeRisk": best_r.route_risk_indicator,
            "unmappedPercentage": best_r.unmapped_percentage
        })

    evaluation_payload = {
        "studyArea": study_area.to_dict(),
        "scenarios": scenario_results,
        "sensitivityLambda": lambda_sensitivity,
        "sensitivityPrior": prior_sensitivity
    }

    # Save to data directory
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "routing_evaluation_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_payload, f, indent=2)

    logger.info(f"Evaluation complete. Results written to {output_path}")
    return evaluation_payload


if __name__ == "__main__":
    run_evaluation()
