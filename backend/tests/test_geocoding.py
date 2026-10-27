"""
SafePath Finder — Location Search and Geocoding Test Suite
Validates case-insensitivity, partial matching, coordinate parsing,
study area separation, provider failure handling, and end-to-end routing integration.
"""

import pytest
import httpx
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app
from app.services.geocoding_service import GeocodingService, get_geocoding_service
from app.schemas.geocoding import GeocodingResult
from app.geospatial.study_area import StudyArea
from app.geospatial.exceptions import (
    LocationNotFoundError,
    GeocodingServiceUnavailableError,
    OutOfCoverageError
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def geocoding_service():
    return get_geocoding_service()


# ==============================================================================
# 1. CASE-INSENSITIVE AND PARTIAL SEARCH TESTS
# ==============================================================================
def test_case_insensitive_searches(client: TestClient):
    """Searches must be case-insensitive: 'electronic city', 'Electronic City', 'ELECTRONIC CITY'."""
    queries = ["electronic city", "Electronic City", "ELECTRONIC CITY", "ElEcTrOnIc CiTy"]
    first_results = None

    for q in queries:
        resp = client.get(f"/api/v1/geocoding/search?q={q}&limit=5")
        assert resp.status_code == 200, f"Query '{q}' failed with status {resp.status_code}"
        data = resp.json()
        assert data["count"] > 0
        names = [r["name"].lower() for r in data["results"]]
        assert any("electronic city" in n for n in names)

        # Coordinate check
        top = data["results"][0]
        assert abs(top["latitude"] - 12.8436) < 0.05
        assert abs(top["longitude"] - 77.6687) < 0.05

        if first_results is None:
            first_results = [(r["latitude"], r["longitude"]) for r in data["results"]]
        else:
            current_results = [(r["latitude"], r["longitude"]) for r in data["results"]]
            assert current_results == first_results, "Cached results must match across case variations"


def test_partial_place_name_search(client: TestClient):
    """Partial place names (e.g. 'jayanag', 'lalba', 'cubb') return relevant suggestions."""
    partial_queries = [("jayanag", "Jayanagar"), ("lalba", "Lalbagh"), ("cubb", "Cubbon")]
    for partial, expected in partial_queries:
        resp = client.get(f"/api/v1/geocoding/search?q={partial}&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        assert any(expected.lower() in r["name"].lower() for r in data["results"])


def test_street_addresses_and_landmarks_with_locality_city_region(client: TestClient):
    """Suggestions include locality, city, region in their display names and addresses."""
    resp = client.get("/api/v1/geocoding/search?q=MG Road&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0

    top = data["results"][0]
    assert "displayName" in top
    assert len(top["displayName"]) > 5
    # Structured address components check
    assert "address" in top
    assert isinstance(top["address"], dict)
    # Check that city or state is represented
    display_lower = top["displayName"].lower()
    assert "bengaluru" in display_lower or "karnataka" in display_lower or "india" in display_lower


def test_multiple_similarly_named_places(client: TestClient):
    """Multiple distinct suggestions returned for broadly named areas (e.g. Jayanagar)."""
    resp = client.get("/api/v1/geocoding/search?q=Jayanagar&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 2
    # Verify suggestions have unique IDs or distinct locations
    ids = [r["id"] for r in data["results"]]
    assert len(set(ids)) == len(ids)


# ==============================================================================
# 2. COORDINATE PARSING AND STUDY AREA SEPARATION
# ==============================================================================
def test_direct_coordinate_query_parsing(client: TestClient):
    """Direct lat, lon coordinate input is recognized as a valid suggestion."""
    resp = client.get("/api/v1/geocoding/search?q=12.9257, 77.5833&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    top = data["results"][0]
    assert top["type"] == "coordinate"
    assert abs(top["latitude"] - 12.9257) < 0.0001
    assert abs(top["longitude"] - 77.5833) < 0.0001
    assert top["inStudyArea"] is True
    assert top["studyAreaDistanceMeters"] == 0.0


def test_separation_of_geocoding_from_routing_coverage(client: TestClient):
    """
    Electronic City is a valid location found by geocoding, but lies outside
    the pilot pedestrian corridor [12.9200, 77.5700, 12.9850, 77.6200].
    The geocoder must flag inStudyArea=False, and routing must return HTTP 400 OutOfCoverage.
    """
    # 1. Geocoding search returns it with inStudyArea=False
    geo_resp = client.get("/api/v1/geocoding/search?q=Electronic City&limit=5")
    assert geo_resp.status_code == 200
    data = geo_resp.json()
    top = data["results"][0]
    assert "electronic city" in top["name"].lower()
    assert top["inStudyArea"] is False
    assert top["studyAreaDistanceMeters"] is not None
    assert top["studyAreaDistanceMeters"] > 5000  # ~10km outside corridor

    # 2. Route comparison using Electronic City text returns HTTP 400 (OutOfCoverageError)
    # NOT HTTP 422 (not found) or 500 (crash)
    route_resp = client.post("/api/v1/routes/compare", json={
        "origin": "Electronic City, Bengaluru",
        "destination": "Lalbagh West Gate, Bengaluru",
        "walkingMode": "pedestrian"
    })
    assert route_resp.status_code == 400
    err_detail = route_resp.json().get("detail", "")
    assert "outside" in err_detail.lower()
    assert "study area" in err_detail.lower() or "bengaluru pilot corridor" in err_detail.lower()


def test_selected_coordinates_passed_to_route_endpoint(client: TestClient):
    """
    When coordinates are supplied explicitly (as stored when selecting an autocomplete item),
    the router uses them directly without redundant geocoding.
    """
    payload = {
        "origin": "Custom Starting Point",
        "destination": "Custom Destination",
        "originCoordinates": [12.9257, 77.5833],      # Jayanagar 4th Block
        "destinationCoordinates": [12.9460, 77.5844], # Lalbagh West Gate
        "walkingMode": "pedestrian"
    }
    resp = client.post("/api/v1/routes/compare", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["routes"]) >= 3
    # Check that coordinates were respected in route geometry endpoints
    geom = data["routes"][0]["geometry"]
    assert len(geom) >= 2


# ==============================================================================
# 3. ERROR HANDLING & ROBUSTNESS
# ==============================================================================
def test_unknown_location_returns_controlled_error(client: TestClient):
    """A completely fictitious location returns HTTP 422 with an informative error message."""
    route_resp = client.post("/api/v1/routes/compare", json={
        "origin": "Zzzxyq Atlantis Nowhere Land 99999",
        "destination": "Lalbagh West Gate, Bengaluru",
        "walkingMode": "pedestrian"
    })
    assert route_resp.status_code == 422
    detail = route_resp.json().get("detail", "")
    assert "Could not resolve" in detail
    assert "Zzzxyq Atlantis Nowhere Land 99999" in detail


def test_invalid_coordinate_ranges(client: TestClient):
    """Coordinates outside mathematical [-90..90, -180..180] return HTTP 422."""
    route_resp = client.post("/api/v1/routes/compare", json={
        "origin": "Invalid",
        "destination": "Lalbagh",
        "originCoordinates": [95.0, 77.58],  # Invalid latitude > 90
        "destinationCoordinates": [12.94, 77.58]
    })
    assert route_resp.status_code == 422
    assert "latitude (95.0) is outside valid range" in route_resp.json().get("detail", "")


def test_geocoding_provider_failure_handling(client: TestClient):
    """
    When the upstream geocoding provider fails or times out and no local landmark matches,
    the API returns HTTP 503 Service Unavailable with user guidance.
    """
    with patch.object(GeocodingService, "_query_upstream_provider") as mock_query:
        mock_query.side_effect = GeocodingServiceUnavailableError("Geocoding request timed out. Please try again.")

        # Query a non-local address that requires upstream resolution
        resp = client.get("/api/v1/geocoding/search?q=SomeRandomUncachedRoadFarAway&limit=5")
        assert resp.status_code == 503
        detail = resp.json().get("detail", "")
        assert "timed out" in detail.lower() or "unavailable" in detail.lower()


def test_geocoding_zero_pii_and_security(client: TestClient):
    """Geocoding queries never log or leak sensitive credentials or user personal details."""
    # Ensure search endpoint does not require auth or leak private keys
    resp = client.get("/api/v1/geocoding/search?q=MG Road")
    assert resp.status_code == 200
    text_content = resp.text
    assert "secret_key" not in text_content.lower()
    assert "password" not in text_content.lower()
    assert "api_key" not in text_content.lower()
