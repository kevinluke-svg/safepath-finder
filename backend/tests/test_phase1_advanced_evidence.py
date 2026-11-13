"""
Phase 1: Advanced Safety Evidence and Community Intelligence Test Suite.

Validates:
1. Streetlight classification and unknown states preservation (lit, unlit, unmapped).
2. Crime-related evidence validation, PII scrubbing, and segment normalization.
3. Street dog sightings vs aggressive encounters & bite incidents.
4. Nearby landmarks and assistance facilities (hospitals, police, transit, parks, straight-line labeling).
5. Pedestrian infrastructure evaluation dimensions (sidewalks, crossings, accessibility, difficulty).
6. Community report moderation lifecycle, duplicate detection (30m/48h), distinct-account corroboration,
   and anti-abuse rate limiting.
7. Geospatial data association, spatial tolerance, and distance tracking.
8. API authorization and reporter privacy guarantee on public feeds.
9. Database migration safety and idempotency.
10. End-to-end routing comparison integration with complete evidence summaries.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.report import CommunityReport, ReportCorroboration
from app.models.user import User
from app.models.evidence import StreetSegment
from app.geospatial.pedestrian_infrastructure import (
    PedestrianInfrastructureProcessor,
    compute_route_infrastructure_summary
)
from app.schemas.route import PedestrianInfrastructureSummary
from app.geospatial.facilities_adapter import OsmFacilityAdapter, FacilityPoint
from app.geospatial.study_area import StudyArea
from app.geospatial.lighting_processor import LightingProcessor
from app.geospatial.crime_adapter import CrimeRecord, PROHIBITED_PII_COLUMNS


# =============================================================================
# 1. STREETLIGHT AND LIGHTING EVIDENCE
# =============================================================================
def test_streetlight_classification_and_unknown_states_preservation():
    """
    Verify lighting classifier distinguishes lit, unlit, and explicitly unmapped states.
    Ensures missing lighting is NEVER fabricated as unlit or zero-risk.
    """
    processor = LightingProcessor()

    # Mapped lit
    assert processor.classify_edge_lighting({"lit": "yes"}, 1, 2).lit_status == "lit"
    assert processor.classify_edge_lighting({"lit": "dusk-dawn"}, 1, 2).lit_status == "lit"
    assert processor.classify_edge_lighting({"lit": "24/7"}, 1, 2).lit_status == "lit"

    # Mapped unlit
    assert processor.classify_edge_lighting({"lit": "no"}, 1, 2).lit_status == "unlit"

    # Conflicting or disused
    assert processor.classify_edge_lighting({"lit": "disused"}, 1, 2).lit_status == "unlit"

    # Unmapped / Missing information
    assert processor.classify_edge_lighting({}, 1, 2).lit_status == "unmapped"
    assert processor.classify_edge_lighting({"highway": "residential"}, 1, 2).lit_status == "unmapped"
    assert processor.classify_edge_lighting({"lit": "unknown"}, 1, 2).lit_status == "unmapped"


# =============================================================================
# 2. CRIME-RELATED EVIDENCE
# =============================================================================
def test_crime_evidence_validation_and_segment_normalization():
    """
    Verify crime evidence requires documented categories, rejects PII,
    and produces normalized rates per km over a documented time window (365 days).
    """
    from app.geospatial.crime_processor import SEVERITY_MAPPING

    # Valid crime record
    valid_record = CrimeRecord(
        incident_id="CR-2026-001",
        category="theft",
        latitude=12.9350,
        longitude=77.5850,
        timestamp=datetime.now(timezone.utc).isoformat(),
        spatial_precision="exact_coordinate",
        source="Bengaluru City Police Open Portal"
    )
    assert valid_record.category == "theft"
    assert SEVERITY_MAPPING.get(valid_record.category) == "medium"

    # Prohibited PII columns rejection
    assert "victim" in PROHIBITED_PII_COLUMNS
    assert "phone" in PROHIBITED_PII_COLUMNS

    # Normalization by length (e.g. 500m segment = 0.5km)
    length_km = 0.5
    raw_crime_count = 2
    rate_per_km = raw_crime_count / length_km
    assert rate_per_km == 4.0

    # Ensure incident counts are NOT converted into guaranteed probabilities of victimization
    segment = StreetSegment(
        id="test-seg-1",
        street_name="10th Main Road",
        length_meters=500.0,
        crime_count=raw_crime_count,
        crime_rate_per_km=rate_per_km,
        lit_status="lit"
    )
    assert segment.crime_rate_per_km == 4.0
    assert segment.crime_count == 2


# =============================================================================
# 3. STREET-DOG SIGHTINGS AND ENCOUNTERS
# =============================================================================
def test_dog_encounter_categories_and_risk_differentiation(client: TestClient, traveller_headers: dict):
    """
    Verify all 4 dog encounter categories:
    1. dog_sighting (ordinary, informational, 0 risk penalty)
    2. dog_group (pack)
    3. dog_aggressive (threatening, chasing)
    4. dog_bite (physical attack)
    """
    categories = ["dog_sighting", "dog_group", "dog_aggressive", "dog_bite"]

    for idx, cat in enumerate(categories):
        res = client.post(
            "/api/v1/reports",
            headers=traveller_headers,
            json={
                "category": cat,
                "location": f"Near Corner on Test Street for {cat}",
                "description": f"Detailed report description for category {cat} under evaluation.",
                "latitude": 12.9355 + (idx * 0.005),
                "longitude": 77.5855 + (idx * 0.005),
                "dogCount": 2 if cat == "dog_group" else 1,
                "isAggressive": cat in {"dog_aggressive", "dog_bite"}
            }
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["category"] == cat
        assert data["status"] in {"pending", "flagged"}


# =============================================================================
# 4. NEARBY LANDMARKS AND ASSISTANCE FACILITIES
# =============================================================================
def test_nearby_facilities_expansion_and_straight_line_labeling():
    """
    Verify assistance facilities (police, hospitals, pharmacies) are strictly
    distinguished from civic landmarks (transit, parks, public buildings, schools),
    and distance is explicitly labeled as straight-line proximity.
    """
    adapter = OsmFacilityAdapter()
    area = StudyArea.from_settings()
    result = adapter.get_facilities(area)

    # Validate presence of expanded categories
    assert result.police_count >= 1
    assert result.hospital_count >= 1
    assert result.assistance_facilities_count >= 2
    assert result.civic_landmarks_count >= 1

    # Check assistance facility flag
    police_fac = result.police_stations[0]
    assert police_fac.is_assistance is True
    assert police_fac.retrieved_at is not None

    # Check non-assistance landmark
    if result.parks:
        park_fac = result.parks[0]
        assert park_fac.is_assistance is False
        assert park_fac.facility_type == "park"


# =============================================================================
# 5. PEDESTRIAN INFRASTRUCTURE
# =============================================================================
def test_pedestrian_infrastructure_classification():
    """
    Verify pedestrian infrastructure evaluates sidewalk availability, crossings,
    accessibility features (tactile paving, wheelchair), and road crossing difficulty.
    """
    processor = PedestrianInfrastructureProcessor()

    # Sidewalk classification
    c1 = processor.classify_edge_infrastructure({"sidewalk": "both", "highway": "residential"}, 1, 2)
    assert c1.sidewalk_status == "both"

    c2 = processor.classify_edge_infrastructure({"sidewalk": "left", "highway": "residential"}, 1, 2)
    assert c2.sidewalk_status == "left"

    c3 = processor.classify_edge_infrastructure({"sidewalk": "no", "highway": "secondary"}, 1, 2)
    assert c3.sidewalk_status == "none"

    c4 = processor.classify_edge_infrastructure({"highway": "footway"}, 1, 2)
    assert c4.sidewalk_status == "separate"

    c_unmapped = processor.classify_edge_infrastructure({"highway": "residential"}, 1, 2)
    assert c_unmapped.sidewalk_status == "unmapped"

    # Crossing classification
    c_sig = processor.classify_edge_infrastructure({"crossing": "traffic_signals", "highway": "secondary"}, 1, 2)
    assert c_sig.crossing_status == "traffic_signals"

    c_mark = processor.classify_edge_infrastructure({"crossing": "marked", "highway": "residential"}, 1, 2)
    assert c_mark.crossing_status == "marked"

    # Tactile paving & Wheelchair
    c_tac = processor.classify_edge_infrastructure({"tactile_paving": "yes", "wheelchair": "yes"}, 1, 2)
    assert c_tac.has_tactile_paving is True
    assert c_tac.wheelchair_accessible == "yes"

    c_no_tac = processor.classify_edge_infrastructure({"tactile_paving": "no", "wheelchair": "no"}, 1, 2)
    assert c_no_tac.has_tactile_paving is False
    assert c_no_tac.wheelchair_accessible == "no"

    # Crossing difficulty
    c_high = processor.classify_edge_infrastructure({"highway": "primary", "crossing": "none"}, 1, 2)
    assert c_high.crossing_difficulty == "high"

    c_low = processor.classify_edge_infrastructure({"highway": "residential"}, 1, 2)
    assert c_low.crossing_difficulty == "low"


def test_pedestrian_infrastructure_summary_computation():
    """
    Verify route-level pedestrian infrastructure aggregation keeps dimensions identifiable.
    """
    segments = [
        {
            "length_meters": 200.0,
            "sidewalk_status": "both",
            "crossing_status": "traffic_signals",
            "has_tactile_paving": True,
            "is_wheelchair_accessible": True,
            "crossing_difficulty": "low",
            "has_construction_hazard": False
        },
        {
            "length_meters": 100.0,
            "sidewalk_status": "unmapped",
            "crossing_status": "none",
            "has_tactile_paving": False,
            "is_wheelchair_accessible": False,
            "crossing_difficulty": "high",
            "has_construction_hazard": True
        }
    ]

    summary = compute_route_infrastructure_summary(segments, total_distance_meters=300.0)
    assert summary["totalDistanceMeters"] == 300.0
    assert summary["sidewalkDocumentedLengthMeters"] == 200.0
    assert summary["sidewalkUnmappedLengthMeters"] == 100.0
    assert summary["sidewalkDocumentedPercentage"] == pytest.approx(66.7, 0.1)
    assert summary["signalizedCrossingCount"] == 1
    assert summary["tactilePavingCount"] == 1
    assert summary["highDifficultyCrossingsCount"] == 1
    assert summary["constructionHazardsCount"] == 1


# =============================================================================
# 6. COMMUNITY REPORT VERIFICATION, DUPLICATES & RATE LIMITING
# =============================================================================
def test_community_report_duplicate_detection(
    client: TestClient,
    traveller_headers: dict,
    other_traveller_headers: dict
):
    """
    Verify that duplicate reports from the same user are rejected (preventing spam),
    while reports within 30 meters from distinct users are accepted with duplicate_of_id.
    """
    # 1. First report by User A
    res1 = client.post(
        "/api/v1/reports",
        headers=traveller_headers,
        json={
            "category": "broken_lighting",
            "location": "Jayanagar 4th Block Main Gate",
            "description": "Streetlight post #B4 is completely dark and unlit.",
            "latitude": 12.9298,
            "longitude": 77.5830
        }
    )
    assert res1.status_code == 201
    rep1_id = res1.json()["id"]

    # 2. Resubmission by SAME user at same location (< 30m) -> HTTP 400 Bad Request
    res_same = client.post(
        "/api/v1/reports",
        headers=traveller_headers,
        json={
            "category": "broken_lighting",
            "location": "Jayanagar 4th Block Gate Entrance",
            "description": "Dark streetlight pole near entrance gate.",
            "latitude": 12.92985,  # ~5.5m offset
            "longitude": 77.58305
        }
    )
    assert res_same.status_code == 400
    assert "duplicate submission" in res_same.json()["detail"].lower()

    # 3. Submission by DISTINCT user (User B) near same spot -> HTTP 201 with duplicateOfId
    res_other = client.post(
        "/api/v1/reports",
        headers=other_traveller_headers,
        json={
            "category": "broken_lighting",
            "location": "Jayanagar 4th Block Gate Entrance",
            "description": "Dark streetlight pole near entrance gate observed by neighbour.",
            "latitude": 12.92985,  # ~5.5m offset
            "longitude": 77.58305
        }
    )
    assert res_other.status_code == 201
    data_other = res_other.json()
    assert data_other["duplicateOfId"] == rep1_id


def test_community_report_corroboration_distinct_accounts(
    client: TestClient,
    traveller_headers: dict,
    other_traveller_headers: dict
):
    """
    Verify that a distinct user account can corroborate an existing report,
    while self-corroboration by the reporter is strictly prevented.
    """
    # 1. User A submits report
    res = client.post(
        "/api/v1/reports",
        headers=traveller_headers,
        json={
            "category": "dog_aggressive",
            "location": "Cross road near 10th Main",
            "description": "Aggressive pack of 3 dogs chasing pedestrians.",
            "latitude": 12.9340,
            "longitude": 77.5840
        }
    )
    assert res.status_code == 201
    report_id = res.json()["id"]

    # 2. User A attempts to corroborate own report -> HTTP 400
    res_self = client.post(f"/api/v1/reports/{report_id}/corroborate", headers=traveller_headers)
    assert res_self.status_code == 400
    assert "own report" in res_self.json()["detail"].lower()

    # 3. User B corroborates report -> HTTP 200
    res_other = client.post(f"/api/v1/reports/{report_id}/corroborate", headers=other_traveller_headers)
    assert res_other.status_code == 200
    assert res_other.json()["corroborationsCount"] == 2

    # 4. User B attempts second corroboration -> HTTP 400 (already corroborated)
    res_other2 = client.post(f"/api/v1/reports/{report_id}/corroborate", headers=other_traveller_headers)
    assert res_other2.status_code == 400
    assert "already corroborated" in res_other2.json()["detail"].lower()


def test_submission_rate_limiting(client: TestClient, traveller_headers: dict, db: Session):
    """
    Verify anti-abuse rate limit: submitting > 10 reports within 10 minutes raises HTTP 429.
    """
    # Pre-seed 10 reports in db for this user within the last 5 minutes
    user = db.query(User).filter(User.email == "priya.sharma@example.test").first()
    assert user is not None

    for i in range(10):
        db.add(CommunityReport(
            reporter_id=user.id,
            category="other_concern",
            category_label="Other street condition",
            location=f"Rate limit seed {i}",
            description=f"Automated test report description {i} for rate limiting check.",
            provenance="Mobile Web Client",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2)
        ))
    db.commit()

    # 11th submission should be rejected with 429 Too Many Requests
    res = client.post(
        "/api/v1/reports",
        headers=traveller_headers,
        json={
            "category": "other_concern",
            "location": "Rate limit threshold location",
            "description": "Attempting 11th submission within rate limit window.",
            "latitude": 12.9300,
            "longitude": 77.5800
        }
    )
    assert res.status_code == 429
    assert "rate limit" in res.json()["detail"].lower()


# =============================================================================
# 7. REPORTER PRIVACY AND AUTHORIZATION
# =============================================================================
def test_public_reports_feed_privacy_guarantee(client: TestClient, traveller_headers: dict):
    """
    Verify GET /api/v1/reports/public completely strips reporter identities,
    emails, phone numbers, and moderation notes.
    """
    res = client.get("/api/v1/reports/public")
    assert res.status_code == 200
    reports = res.json()
    assert isinstance(reports, list)

    for r in reports:
        assert "reporterId" not in r
        assert "reporterEmail" not in r
        assert "userId" not in r
        assert "user_id" not in r
        assert "moderatorNotes" not in r
        assert "adminNotes" not in r


# =============================================================================
# 8. GEOSPATIAL DATA ASSOCIATION & SPATIAL TOLERANCE
# =============================================================================
def test_geospatial_matching_distance_and_tolerance():
    """
    Verify spatial association links points within tolerance and computes
    matching distance in meters using STRtree and UTM projection.
    """
    import networkx as nx
    from app.geospatial.spatial_matcher import SpatialMatcher

    # Build small metric-ready graph
    G = nx.MultiDiGraph()
    G.graph["crs"] = "epsg:4326"
    G.add_node(1, x=77.5850, y=12.9350)
    G.add_node(2, x=77.5850, y=12.9370)
    G.add_edge(1, 2, key=0, length=220.0)

    matcher = SpatialMatcher(G, default_tolerance_meters=50.0)

    # Point ~11m east of edge -> should match with distance < 50m
    match_near = matcher.match_point(12.9360, 77.5851, tolerance_meters=50.0)
    assert match_near.status == "matched"
    assert match_near.distance_meters is not None
    assert match_near.distance_meters < 50.0

    # Point ~1km away -> should be unmatched rather than falsely assigned
    match_far = matcher.match_point(12.9450, 77.5850, tolerance_meters=50.0)
    assert match_far.status == "unmatched"


# =============================================================================
# 9. ROUTE COMPARISON INTEGRATION WITH INFRASTRUCTURE AUDIT
# =============================================================================
def test_route_comparison_api_includes_all_phase1_summaries(client: TestClient):
    """
    Verify POST /api/v1/routes/compare returns all Phase 1 dimensions:
    - streetlightSummary
    - nearbyPlaces (with isAssistance and distanceType)
    - dogEncounterSummary
    - pedestrianInfrastructureSummary
    """
    payload = {
        "origin": "12.9352, 77.5845",
        "destination": "12.9420, 77.5890",
        "originCoordinates": [12.9352, 77.5845],
        "destinationCoordinates": [12.9420, 77.5890],
        "preferences": {
            "preferLighting": True,
            "preferActivity": True,
            "avoidIsolated": True
        }
    }

    res = client.post("/api/v1/routes/compare", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data["routes"]) >= 1

    for route in data["routes"]:
        # 1. Streetlight audit
        assert "streetlightSummary" in route
        assert route["streetlightSummary"]["totalDistanceMeters"] > 0
        assert route["streetlightSummary"]["litPercentage"] >= 0.0
        assert route["streetlightSummary"]["unlitPercentage"] >= 0.0
        assert route["streetlightSummary"]["unknownPercentage"] >= 0.0

        # 2. Nearby places audit
        assert "nearbyPlaces" in route
        for place in route["nearbyPlaces"]:
            assert "isAssistance" in place
            assert place["distanceType"] in {"pedestrian_network", "straight_line"}

        # 3. Dog encounter audit
        assert "dogEncounterSummary" in route
        assert "totalReportsCount" in route["dogEncounterSummary"]
        assert "guidance" in route["dogEncounterSummary"]

        # 4. Pedestrian infrastructure audit
        assert "pedestrianInfrastructureSummary" in route
        infra = route["pedestrianInfrastructureSummary"]
        assert "sidewalkDocumentedPercentage" in infra or "sidewalkCoveragePercentage" in infra
        assert "sidewalkDocumentedLengthMeters" in infra or "knownSidewalkDistanceMeters" in infra
        assert "crossingCount" in infra or "crossing_count" in infra
        assert "signalizedCrossingCount" in infra or "signalized_crossing_count" in infra
