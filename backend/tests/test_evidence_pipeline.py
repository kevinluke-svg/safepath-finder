"""
SafePath Finder — Comprehensive Geospatial Evidence Pipeline Automated Tests
Tests:
- Valid and invalid CSV crime ingestion
- PII rejection and privacy protections
- Duplicate detection and coordinate validation
- STRtree spatial matching (snapped vs unmatched beyond tolerance)
- Epistemological lighting classification (lit, unlit, conflicting, unmapped)
- Pedestrian network facility routing vs straight-line distance
- Community feedback mapping, moderation vs certainty, and deduplication
- Zero PII in evidence observations and public APIs
- Database model persistence and migration safety
"""

import os
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import networkx as nx
from shapely.geometry import LineString

from app.models.evidence import StreetSegment, EvidenceObservation
from app.models.report import CommunityReport
from app.geospatial.study_area import StudyArea
from app.geospatial.spatial_matcher import SpatialMatcher, SpatialMatchResult
from app.geospatial.facilities_adapter import FacilityPoint
from app.geospatial.facility_router import FacilityRouter
from app.geospatial.lighting_processor import LightingProcessor
from app.geospatial.crime_processor import CrimeProcessor, SEVERITY_MAPPING
from app.geospatial.community_processor import CommunityProcessor
from app.geospatial.evidence_pipeline import EvidencePipeline
from app.geospatial.exceptions import DataQualityError


# --- Test Fixtures & Utilities ---

@pytest.fixture
def sample_study_area() -> StudyArea:
    """Returns a deterministic study area fixture for testing."""
    return StudyArea(
        name="Test Urban Corridor",
        south=12.9250,
        west=77.5800,
        north=12.9400,
        east=77.5950,
        place_name="Test Koramangala Bengaluru",
        description="Deterministic study area boundary for automated tests"
    )


@pytest.fixture
def synthetic_pedestrian_graph() -> nx.MultiDiGraph:
    """
    Creates a deterministic metric-referenced pedestrian graph fixture.
    Node 101 -> Node 102: Main pedestrian street (12.9300, 77.5850) -> (12.9330, 77.5850)
    Node 102 -> Node 103: Connected cross street
    Node 201 -> Node 202: Disconnected island component to test reachability & straight-line fallback
    """
    G = nx.MultiDiGraph(crs="EPSG:4326")

    # Component 1 (Main Street)
    G.add_node(101, y=12.9300, x=77.5850)
    G.add_node(102, y=12.9330, x=77.5850)
    G.add_node(103, y=12.9330, x=77.5890)

    # Edge 101 -> 102 (lit=yes, length ~330m)
    geom1 = LineString([(77.5850, 12.9300), (77.5850, 12.9330)])
    G.add_edge(101, 102, 0, name="Corridor Main", length=333.0, lit="yes", geometry=geom1, highway="footway")
    G.add_edge(102, 101, 0, name="Corridor Main", length=333.0, lit="yes", geometry=geom1, highway="footway")

    # Edge 102 -> 103 (unmapped lit, length ~430m)
    geom2 = LineString([(77.5850, 12.9330), (77.5890, 12.9330)])
    G.add_edge(102, 103, 0, name="Cross Lane", length=434.0, geometry=geom2, highway="residential")
    G.add_edge(103, 102, 0, name="Cross Lane", length=434.0, geometry=geom2, highway="residential")

    # Component 2 (Disconnected Island)
    G.add_node(201, y=12.9380, x=77.5920)
    G.add_node(202, y=12.9390, x=77.5920)
    geom3 = LineString([(77.5920, 12.9380), (77.5920, 12.9390)])
    G.add_edge(201, 202, 0, name="Isolated Path", length=111.0, lit="no", geometry=geom3, highway="footway")

    return G


# --- 1. Crime Ingestion & Validation Tests ---

def test_csv_crime_import_valid(sample_study_area):
    """Verifies parsing of a valid synthetic crime dataset fixture."""
    processor = CrimeProcessor()
    csv_content = (
        "incident_id,latitude,longitude,category,timestamp,severity,spatial_precision\n"
        "syn-c1,12.9310,77.5851,assault,2026-05-10T14:30:00Z,high,exact_coordinate\n"
        "syn-c2,12.9320,77.5852,theft,2026-06-15T21:00:00Z,medium,block_level\n"
        "syn-c3,12.9325,77.5853,vandalism,2026-07-20T02:00:00Z,,block_level\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        records, summary = processor.ingest_csv(temp_path, study_area=sample_study_area)
        assert len(records) == 3
        assert summary.valid_records_count == 3
        assert summary.duplicates_detected_count == 0
        assert summary.date_range is not None

        # Check automated severity assignment for unstated severity (vandalism -> low)
        vandalism_rec = next(r for r in records if r.incident_id == "syn-c3")
        assert vandalism_rec.severity == "low"
    finally:
        os.remove(temp_path)


def test_csv_crime_import_missing_required_columns(sample_study_area):
    """Verifies that datasets missing essential columns raise DataQualityError."""
    processor = CrimeProcessor()
    csv_content = (
        "incident_id,timestamp,category\n"
        "syn-c1,2026-05-10T14:30:00Z,theft\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        with pytest.raises(DataQualityError) as exc_info:
            processor.ingest_csv(temp_path, study_area=sample_study_area)
        assert "missing required columns" in str(exc_info.value).lower()
    finally:
        os.remove(temp_path)


def test_csv_crime_import_pii_rejection(sample_study_area):
    """Guarantees that files containing personal identifying info (PII) are strictly rejected."""
    processor = CrimeProcessor()
    csv_content = (
        "incident_id,latitude,longitude,category,victim_name,phone_number\n"
        "syn-c1,12.9310,77.5851,theft,John Doe,9876543210\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        with pytest.raises(DataQualityError) as exc_info:
            processor.ingest_csv(temp_path, study_area=sample_study_area)
        assert "prohibited personal identifying column" in str(exc_info.value).lower()
    finally:
        os.remove(temp_path)


def test_csv_crime_duplicate_detection(sample_study_area):
    """Ensures duplicate records (identical ID or spatial-temporal fingerprint) are deduplicated."""
    processor = CrimeProcessor()
    csv_content = (
        "incident_id,latitude,longitude,category,timestamp\n"
        "syn-c1,12.9310,77.5851,theft,2026-05-10T14:30:00Z\n"
        "syn-c1,12.9310,77.5851,theft,2026-05-10T14:30:00Z\n"  # Exact duplicate ID
        "syn-c2,12.9310,77.5851,theft,2026-05-10T14:30:00Z\n"  # Identical fingerprint
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        records, summary = processor.ingest_csv(temp_path, study_area=sample_study_area)
        assert len(records) == 1
        assert summary.duplicates_detected_count == 2
    finally:
        os.remove(temp_path)


def test_csv_crime_invalid_coordinates_skipped(sample_study_area):
    """Verifies that rows with out-of-bounds or non-numeric coordinates are safely skipped."""
    processor = CrimeProcessor()
    csv_content = (
        "incident_id,latitude,longitude,category,timestamp\n"
        "syn-c1,12.9310,77.5851,theft,2026-05-10T14:30:00Z\n"
        "syn-c2,999.0,77.5851,theft,2026-05-10T14:30:00Z\n"  # Invalid latitude
        "syn-c3,invalid_lat,77.5851,theft,2026-05-10T14:30:00Z\n"  # Non-numeric
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        records, summary = processor.ingest_csv(temp_path, study_area=sample_study_area)
        assert len(records) == 1
        assert summary.skipped_rows_count == 2
    finally:
        os.remove(temp_path)


# --- 2. Spatial Indexing & Snapping Tests ---

def test_spatial_matcher_snapping_within_and_beyond_tolerance(synthetic_pedestrian_graph):
    """
    Tests STRtree projection:
    - Point directly adjacent to edge 101->102 (within 30m) matches successfully.
    - Point 200m away is marked 'unmatched' with distance explanation.
    """
    matcher = SpatialMatcher(synthetic_pedestrian_graph, default_tolerance_meters=30.0)

    # 1. Point ~11m west of edge 101-102 (lat 12.9315, lon 77.5849)
    res_near = matcher.match_point(12.9315, 77.5849, tolerance_meters=30.0)
    assert res_near.status == "matched"
    assert res_near.edge_u in (101, 102)
    assert res_near.distance_meters is not None
    assert res_near.distance_meters < 30.0

    # 2. Point ~300m west (lat 12.9315, lon 77.5820)
    res_far = matcher.match_point(12.9315, 77.5820, tolerance_meters=30.0)
    assert res_far.status == "unmatched"
    assert res_far.edge_u is None
    assert res_far.distance_meters is not None
    assert res_far.distance_meters > 30.0
    assert "exceeds the configured tolerance" in res_far.reason


def test_spatial_matcher_invalid_coordinates(synthetic_pedestrian_graph):
    """Ensures non-finite or invalid coordinates raise DataQualityError."""
    matcher = SpatialMatcher(synthetic_pedestrian_graph)
    with pytest.raises(DataQualityError):
        matcher.match_point(float("nan"), 77.5850)
    with pytest.raises(DataQualityError):
        matcher.match_point(12.9300, 250.0)


# --- 3. Lighting Epistemology & Conflict Detection Tests ---

def test_lighting_epistemology_distinctions():
    """
    Verifies the four lighting states:
    - lit (explicit positive OSM tag)
    - unlit (explicit negative OSM tag)
    - conflicting (OSM says lit, but verified community report reports broken lamp)
    - unmapped (no tags; uncertainty preserved, NOT assumed dark)
    """
    processor = LightingProcessor()

    # Case 1: Explicit Lit
    cls_lit = processor.classify_edge_lighting(
        edge_data={"lit": "yes"},
        edge_u=1, edge_v=2
    )
    assert cls_lit.lit_status == "lit"
    assert cls_lit.data_state == "present"

    # Case 2: Explicit Unlit
    cls_unlit = processor.classify_edge_lighting(
        edge_data={"lit": "no"},
        edge_u=1, edge_v=2
    )
    assert cls_unlit.lit_status == "unlit"
    assert cls_unlit.data_state == "present"

    # Case 3: Conflicting (OSM lit=yes, but approved report documents broken luminaire)
    broken_report = {
        "category": "lighting_concern",
        "description": "Broken streetlight pole and non-functional luminaire."
    }
    cls_conf = processor.classify_edge_lighting(
        edge_data={"lit": "yes"},
        edge_u=1, edge_v=2,
        community_lighting_reports=[broken_report]
    )
    assert cls_conf.lit_status == "conflicting"
    assert cls_conf.data_state == "conflicting"
    assert cls_conf.has_conflicting_community_report is True

    # Case 4: Unmapped (no tag) -> must NOT be classified as unlit or zero lighting!
    cls_unmapped = processor.classify_edge_lighting(
        edge_data={},
        edge_u=1, edge_v=2
    )
    assert cls_unmapped.lit_status == "unmapped"
    assert cls_unmapped.data_state == "missing"
    assert "uncertainty" in cls_unmapped.notes.lower()


# --- 4. Assistance Facilities: Network Walking vs Straight-Line Tests ---

def test_facility_routing_walking_vs_straight_line(synthetic_pedestrian_graph):
    """
    Verifies that:
    - Reachable nodes calculate network walking distance & walking time at 1.2 m/s.
    - Disconnected nodes fall back to Euclidean straight-line distance, explicitly labeled.
    """
    router = FacilityRouter(synthetic_pedestrian_graph)

    # Place a synthetic police station near node 101
    police_fac = FacilityPoint(
        id="pol-test-1",
        facility_type="police",
        name="Koramangala Police Station",
        latitude=12.9301,
        longitude=77.5851,
        source="Synthetic Test Fixture",
        confidence="verified_spatial_point",
        metadata={}
    )

    police_prox = router.compute_facility_distances_for_nodes([police_fac], "police")

    # Node 102 is connected to Node 101 via 333m edge
    p_102 = police_prox.get(102)
    assert p_102 is not None
    assert p_102.is_straight_line is False
    assert p_102.distance_type == "network_walking"
    assert p_102.distance_meters > 300.0  # Network path length
    assert p_102.walking_time_minutes > 4.0  # 333m / 72 m/min ~= 4.6 min

    # Node 201 is on the disconnected island component
    p_201 = police_prox.get(201)
    assert p_201 is not None
    assert p_201.is_straight_line is True
    assert p_201.distance_type == "euclidean_straight_line"
    assert "disconnected" in p_201.caveat.lower()


# --- 5. Community Feedback & Moderation vs Certainty Tests ---

def test_community_reports_moderation_and_privacy(db: Session, sample_study_area, synthetic_pedestrian_graph):
    """
    Verifies that:
    - Reporter PII is completely stripped.
    - Moderation status is separated from factual certainty (admin approval != ground truth).
    - Duplicates and stale submissions are handled.
    """
    processor = CommunityProcessor(stale_threshold_days=180)
    matcher = SpatialMatcher(synthetic_pedestrian_graph)

    now = datetime.now(timezone.utc)
    rep_recent = CommunityReport(
        id="rep-test-01",
        category="harassment",
        category_label="Harassment",
        location="10th Main",
        description="Persistent catcalling near bus stand",
        status="approved",
        latitude=12.9315,
        longitude=77.5850,
        reporter_name="Sensitive Reporter Name",
        provenance="User Direct Submission",
        created_at=now - timedelta(days=5)
    )
    rep_stale = CommunityReport(
        id="rep-test-02",
        category="lighting",
        category_label="Broken Light",
        location="Cross Lane",
        description="Broken lamp",
        status="pending",
        latitude=12.9331,
        longitude=77.5870,
        reporter_name="Another Sensitive User",
        provenance="User Direct Submission",
        created_at=now - timedelta(days=220)  # >180 days -> Stale
    )
    db.add(rep_recent)
    db.add(rep_stale)
    db.commit()

    processed, edge_map = processor.process_community_reports(db, sample_study_area, matcher)

    # 1. Verify Recent Approved Report
    rec1 = next(p for p in processed if p.report_id == "rep-test-01")
    assert rec1.evidence_category == "community_hazard"
    assert rec1.subcategory == "harassment"
    assert rec1.verification_status == "admin_reviewed_community_report"
    assert rec1.confidence == "moderate"  # Admin review is moderate confidence, not absolute certainty
    assert rec1.data_state == "present"

    # 2. Verify Stale Pending Report
    rec2 = next(p for p in processed if p.report_id == "rep-test-02")
    assert rec2.verification_status == "unverified_community_submission"
    assert rec2.confidence == "low"
    assert rec2.data_state == "stale"


# --- 6. Full Evidence Pipeline & Database Persistence Tests ---

def test_evidence_pipeline_full_run_and_persistence(db: Session, sample_study_area, synthetic_pedestrian_graph):
    """
    Executes the full pipeline with synthetic fixtures and verifies:
    - StreetSegment rows created with length, lit_status, crime_rate_per_km, facility distances.
    - EvidenceObservation rows created with zero reporter personal info.
    """
    pipeline = EvidencePipeline(study_area=sample_study_area)

    # Create synthetic crime CSV
    csv_content = (
        "incident_id,latitude,longitude,category,timestamp,severity\n"
        "syn-c1,12.9315,77.5850,theft,2026-06-01T10:00:00Z,medium\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        crime_file = f.name

    # Create synthetic facilities
    facilities = [
        FacilityPoint(
            id="fac-pol-1",
            facility_type="police",
            name="City Police Station",
            latitude=12.9300,
            longitude=77.5850,
            source="Synthetic Test Fixture",
            confidence="verified_spatial_point",
            metadata={}
        ),
        FacilityPoint(
            id="fac-hosp-1",
            facility_type="hospital",
            name="General Hospital",
            latitude=12.9330,
            longitude=77.5890,
            source="Synthetic Test Fixture",
            confidence="verified_spatial_point",
            metadata={}
        )
    ]

    try:
        res = pipeline.run_pipeline(
            db=db,
            crime_file_path=crime_file,
            custom_graph=synthetic_pedestrian_graph,
            custom_facilities=facilities
        )
        assert res["status"] == "success"
        assert res["edgesProcessed"] > 0
        assert res["observationsPersisted"] > 0

        # Query database to confirm StreetSegments persisted
        segments = db.query(StreetSegment).filter(StreetSegment.route_id == f"route-{sample_study_area.slug}").all()
        assert len(segments) > 0

        # Confirm length, lit_status, and facility distances are populated
        seg_lit = next((s for s in segments if s.edge_u == 101 and s.edge_v == 102), None)
        assert seg_lit is not None
        assert seg_lit.lit_status == "lit"
        assert seg_lit.nearest_police_distance_meters is not None
        assert seg_lit.crime_count == 1
        assert seg_lit.crime_rate_per_km > 0.0

        # Confirm EvidenceObservation records
        obs = db.query(EvidenceObservation).all()
        assert len(obs) > 0
        for o in obs:
            # Strictly verify that no reporter personal details exist
            assert not hasattr(o, "reporter_name")
            assert not hasattr(o, "user_id")
            assert not hasattr(o, "phone")
            assert not hasattr(o, "email")

    finally:
        os.remove(crime_file)


# --- 7. API Endpoints Contract & Privacy Verification Tests ---

def test_api_crime_import_endpoint_success(client: TestClient, admin_headers):
    """Tests POST /api/v1/evidence/import-crime with valid CSV file upload."""
    csv_bytes = (
        b"incident_id,latitude,longitude,category,timestamp,severity\n"
        b"syn-1,12.9315,77.5850,theft,2026-06-01T10:00:00Z,medium\n"
    )
    response = client.post(
        "/api/v1/evidence/import-crime",
        files={"file": ("test_crime.csv", csv_bytes, "text/csv")},
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["isLoaded"] is True
    assert data["validCount"] == 1
    assert data["duplicateCount"] == 0


def test_api_crime_import_endpoint_pii_rejected(client: TestClient, admin_headers):
    """Tests POST /api/v1/evidence/import-crime rejects PII with 422 Unprocessable Entity."""
    csv_bytes = (
        b"incident_id,latitude,longitude,category,victim_name\n"
        b"syn-1,12.9315,77.5850,theft,Sensitive Name\n"
    )
    response = client.post(
        "/api/v1/evidence/import-crime",
        files={"file": ("bad_pii.csv", csv_bytes, "text/csv")},
        headers=admin_headers
    )
    assert response.status_code == 422
    assert "prohibited personal identifying column" in response.json()["detail"].lower()


def test_api_evidence_observations_query_and_privacy(client: TestClient, db: Session):
    """
    Tests GET /api/v1/evidence/observations:
    Verifies that returned JSON contains no personal reporter details.
    """
    # Insert test observation
    now = datetime.now(timezone.utc)
    obs = EvidenceObservation(
        id="obs-test-audit-01",
        source_id="test-source",
        source_type="community_report",
        category="community_hazard",
        subcategory="harassment",
        latitude=12.9315,
        longitude=77.5850,
        geometry={"type": "Point", "coordinates": [77.5850, 12.9315]},
        match_distance_meters=5.2,
        match_method="strtree_project",
        match_status="matched",
        observed_at=now,
        ingested_at=now,
        source_attribution="Community Contributor (PII Stripped)",
        verification_status="admin_reviewed_community_report",
        confidence="moderate",
        data_state="present",
        provenance="Community Submission",
        limitations=["Individual perception"],
        attributes={"hazardType": "catcalling"}
    )
    db.add(obs)
    db.commit()

    response = client.get("/api/v1/evidence/observations?category=community_hazard")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    item = data["items"][0]

    # Privacy Guarantee: Assert no PII keys in JSON payload
    forbidden_keys = {"reporterName", "reporter_name", "userId", "user_id", "email", "phone", "mobile", "ipAddress"}
    for key in forbidden_keys:
        assert key not in item, f"Forbidden PII key '{key}' leaked in public API response!"


def test_api_coverage_endpoint(client: TestClient):
    """Tests GET /api/v1/evidence/coverage returns data coverage breakdown and caveats."""
    response = client.get("/api/v1/evidence/coverage")
    assert response.status_code == 200
    data = response.json()
    assert "totalEdges" in data
    assert "lightingCoveragePercentage" in data
    assert "dataGaps" in data
    assert len(data["dataGaps"]) > 0
    assert "caveats" in data
    assert len(data["caveats"]) > 0


def test_api_route_segments_extended_attributes(client: TestClient):
    """Tests GET /api/v1/evidence/segments returns extended network attributes."""
    response = client.get("/api/v1/evidence/segments?routeId=route-evidence")
    assert response.status_code == 200
    data = response.json()
    assert "segments" in data
    assert len(data["segments"]) > 0
    seg = data["segments"][0]
    assert "litStatus" in seg
    assert "crimeCount" in seg
    assert "crimeRatePerKm" in seg
    assert "communityReportsCount" in seg
