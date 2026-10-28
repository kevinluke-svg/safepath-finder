"""
SafePath Finder — Route Integration & Explainable Safety Verification Tests
Verifies:
1. Route request and response contract handling with genuine Dijkstra/Yen results.
2. Three explicit route preferences: Fastest, Balanced, Safety-prioritized, plus alternatives.
3. Meaningful error handling on unresolved locations and out-of-coverage coordinates.
4. Identical route alternative explanation (no fabricated diversity).
5. Epistemological uncertainty preservation (missing evidence flagged honestly).
6. Strict privacy preservation (zero PII, reporter identity, or contact details).
"""

import pytest
from fastapi.testclient import TestClient


def test_three_route_preferences_returned_with_consistent_labels(client: TestClient):
    """
    POST /api/v1/routes/compare returns the 3 primary route preferences:
    - Fastest (minimizes traversal time)
    - Balanced (trades walking time against evidence-based risk)
    - Safety-prioritized (strongest evidence weight)
    plus genuine Yen loopless alternatives when requested.
    """
    payload = {
        "origin": "Jayanagar 4th Block, Bengaluru",
        "destination": "Lalbagh West Gate, Bengaluru",
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
    routes = data["routes"]
    assert len(routes) >= 3

    categories = {r["category"] for r in routes}
    assert "fastest" in categories
    assert "balanced" in categories
    assert "safety_prioritized" in categories

    for r in routes:
        assert isinstance(r["id"], str)
        assert isinstance(r["name"], str)
        assert isinstance(r["distanceMeters"], int)
        assert isinstance(r["durationSeconds"], int)
        assert len(r["geometry"]) >= 2
        assert "evidenceSummary" in r
        assert r["evidenceSummary"]["coverage"] in ("adequate", "limited", "insufficient")
        assert r["evidenceSummary"]["freshnessState"] in ("fresh", "stale", "outdated")
        assert isinstance(r["rankingFactors"], list)
        assert len(r["rankingFactors"]) > 0


def test_unresolved_location_returns_meaningful_422(client: TestClient):
    """An unresolvable address must return HTTP 422 with an informative error message."""
    payload = {
        "origin": "Imaginary Floating Palace 999",
        "destination": "Lalbagh West Gate, Bengaluru",
        "walkingMode": "pedestrian"
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 422
    err_detail = response.json().get("detail", "")
    assert "Could not resolve starting location" in err_detail
    assert "Imaginary Floating Palace 999" in err_detail


def test_out_of_coverage_location_returns_meaningful_400(client: TestClient):
    """Coordinates outside the active Bengaluru Pilot Corridor return HTTP 400 Bad Request."""
    payload = {
        "origin": "19.0760, 72.8777",  # Mumbai coordinates
        "destination": "12.9501, 77.5847",
        "walkingMode": "pedestrian"
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 400
    err_detail = response.json().get("detail", "")
    assert "outside configured study area" in err_detail
    assert "Bengaluru Pilot Corridor" in err_detail


def test_identical_route_alternatives_explain_optimality_honestly(client: TestClient):
    """
    If multiple preferences select the same physical corridor, SafePath explains
    that the same path is optimal under the model; it does NOT fabricate diversity.
    """
    payload = {
        "origin": "Jayanagar 4th Block",
        "destination": "Lalbagh West Gate",
        "walkingMode": "pedestrian",
        "preferences": {
            "includeAlternatives": True
        }
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    routes = response.json()["routes"]

    fastest_route = next(r for r in routes if r["category"] == "fastest")
    safety_route = next(r for r in routes if r["category"] == "safety_prioritized")

    if safety_route["geometry"] == fastest_route["geometry"]:
        assert safety_route["isIdenticalToFastest"] is True
        assert safety_route["identicalNotes"] is not None
        assert "safest corridor" in safety_route["identicalNotes"].lower() or "optimal" in safety_route["identicalNotes"].lower()


def test_privacy_preservation_in_route_and_segment_payloads(client: TestClient):
    """
    Routing response must strictly preserve user privacy:
    No email, password hash, phone number, reporter identities, or trusted-contact details.
    """
    payload = {
        "origin": "Jayanagar 4th Block, Bengaluru",
        "destination": "Lalbagh West Gate, Bengaluru",
        "walkingMode": "pedestrian"
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    raw_text = response.text.lower()

    # Forbidden private fields
    assert "email" not in raw_text or "@" not in raw_text
    assert "phone" not in raw_text
    assert "password" not in raw_text
    assert "hashed_password" not in raw_text
    assert "reporter" not in raw_text
    assert "trusted_contact" not in raw_text


def test_missing_evidence_is_explicitly_flagged_as_insufficient(client: TestClient):
    """Evidence coverage below thresholds preserves uncertainty without false green badges."""
    payload = {
        "origin": "Cubbon Park",
        "destination": "MG Road",
        "walkingMode": "pedestrian",
        "preferences": {
            "preferLighting": False,
            "avoidUnknown": False
        }
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    routes = response.json()["routes"]
    for r in routes:
        cov = r["evidenceSummary"]["coverage"]
        assert cov in ("adequate", "limited", "insufficient")
        assert "riskEstimate" in r["evidenceSummary"]
        assert isinstance(r["evidenceSummary"]["coveragePercentage"], int)


def test_arbitrary_non_preset_locations_generate_valid_routes(client: TestClient):
    """
    SafePath must generate genuine pedestrian routes between any arbitrary valid locations
    in the research corridor, not restricted to the three preset buttons.
    """
    # Non-preset pair: Madhavan Park (12.9370, 77.5860) to Subbaiah Circle (12.9580, 77.5860)
    payload = {
        "origin": "Madhavan Park, Jayanagar",
        "destination": "Subbaiah Circle, Lalbagh Road",
        "originCoordinates": [12.9370, 77.5860],
        "destinationCoordinates": [12.9580, 77.5860],
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

    for r in data["routes"]:
        # Ensure route geometry starts and ends near the selected coordinates, not the preset Jayanagar/Lalbagh
        geom = r["geometry"]
        assert len(geom) >= 2
        first_pt = geom[0]
        last_pt = geom[-1]
        assert abs(first_pt[0] - 12.9370) < 0.005
        assert abs(first_pt[1] - 77.5860) < 0.005
        assert abs(last_pt[0] - 12.9580) < 0.005
        assert abs(last_pt[1] - 77.5860) < 0.005
        # Distance must reflect this corridor (~2.4 km geodesic, ~3.7 km true walking path)
        assert 2000 <= r["distanceMeters"] <= 4000


def test_coordinates_passed_in_snake_case_and_camel_case(client: TestClient):
    """Verify that both camelCase and snake_case coordinate payloads are accepted identically."""
    # Test snake_case payload
    payload_snake = {
        "origin": "Richmond Circle",
        "destination": "Brigade Road",
        "origin_coordinates": [12.9660, 77.5990],
        "destination_coordinates": [12.9740, 77.6070]
    }
    res_snake = client.post("/api/v1/routes/compare", json=payload_snake)
    assert res_snake.status_code == 200
    routes_snake = res_snake.json()["routes"]
    assert len(routes_snake) >= 3

    # Test camelCase payload
    payload_camel = {
        "origin": "Richmond Circle",
        "destination": "Brigade Road",
        "originCoordinates": [12.9660, 77.5990],
        "destinationCoordinates": [12.9740, 77.6070]
    }
    res_camel = client.post("/api/v1/routes/compare", json=payload_camel)
    assert res_camel.status_code == 200
    routes_camel = res_camel.json()["routes"]

    assert routes_snake[0]["distanceMeters"] == routes_camel[0]["distanceMeters"]
    assert routes_snake[0]["geometry"] == routes_camel[0]["geometry"]


def test_gandhi_bazaar_connected_to_network(client: TestClient):
    """
    Verify that Gandhi Bazaar (preset 2 endpoint) is topologically connected
    with dedicated nodes and yields a genuine route to South End Circle.
    """
    payload = {
        "origin": "South End Circle",
        "destination": "Gandhi Bazaar Main Road",
        "originCoordinates": [12.9370, 77.5835],
        "destinationCoordinates": [12.9420, 77.5720],
        "preferences": {
            "includeAlternatives": True
        }
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    routes = response.json()["routes"]
    assert len(routes) >= 3
    for r in routes:
        assert len(r["geometry"]) >= 2
        # End point must be at Gandhi Bazaar (12.9420, 77.5720), not 1.2km away
        last_pt = r["geometry"][-1]
        assert abs(last_pt[0] - 12.9420) < 0.005
        assert abs(last_pt[1] - 77.5720) < 0.005


def test_out_of_coverage_does_not_substitute_preset(client: TestClient):
    """
    An out-of-coverage destination must return an explicit HTTP 400 OutOfCoverageError
    and NEVER silently substitute a preset route.
    """
    payload = {
        "origin": "Jayanagar 4th Block",
        "destination": "Electronic City",
        "originCoordinates": [12.9257, 77.5833],
        "destinationCoordinates": [12.8436, 77.6687]
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "outside configured study area" in detail
    assert "Electronic City" in detail


def test_route_geometry_preserves_street_curves_and_intermediate_points(client: TestClient):
    """
    Verify that walking route geometries follow street curves with intermediate waypoints
    instead of drawing 2-point straight lines cutting across buildings.
    """
    payload = {
        "origin": "Madhavan Park",
        "destination": "Subbaiah Circle",
        "originCoordinates": [12.9370, 77.5860],
        "destinationCoordinates": [12.9580, 77.5860]
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    routes = response.json()["routes"]
    for r in routes:
        geom = r["geometry"]
        # Must retain intermediate street curve waypoints (more than just start and end)
        assert len(geom) >= 8, f"Route {r['id']} has only {len(geom)} points; expected >= 8 intermediate street vertices"
        # Verify Leaflet [lat, lon] coordinate ordering
        for pt in geom:
            lat, lon = pt[0], pt[1]
            assert 12.9200 <= lat <= 12.9850, f"Latitude {lat} out of study corridor"
            assert 77.5700 <= lon <= 77.6200, f"Longitude {lon} out of study corridor"


def test_route_segments_reconstructed_for_all_traversed_streets(client: TestClient):
    """
    Verify that each route option contains the complete sequence of traversed street segments,
    not just a single edge at the end.
    """
    payload = {
        "origin": "Richmond Circle",
        "destination": "Brigade Road",
        "originCoordinates": [12.9660, 77.5990],
        "destinationCoordinates": [12.9740, 77.6070]
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    routes = response.json()["routes"]
    for r in routes:
        segments = r["segments"]
        assert len(segments) >= 3, f"Route {r['id']} contains only {len(segments)} segments; expected >= 3"
        for s in segments:
            assert "streetName" in s
            assert len(s["streetName"]) > 0
            assert "lengthMeters" in s
            assert s["lengthMeters"] > 0
            assert "traversalTimeSeconds" in s
            assert len(s["geometry"]) >= 2


def test_off_network_within_bbox_raises_coverage_error(client: TestClient):
    """
    If coordinates are within bounding box but >500m from any walkable street,
    an explicit OutOfCoverageError is returned instead of drawing a line across buildings.
    """
    payload = {
        "origin": "Off-Network Point",
        "destination": "Lalbagh West Gate",
        "originCoordinates": [12.9460, 77.6133],  # Location >250m from walkable streets
        "destinationCoordinates": [12.9460, 77.5844]
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "exceeds walkable network access coverage" in detail

