"""
SafePath Finder — Geospatial Routing Foundation & Data Readiness Audit Tests
"""

import os
import tempfile
import pytest
import networkx as nx
from unittest.mock import patch, MagicMock

from app.geospatial.study_area import StudyArea
from app.geospatial.exceptions import (
    InvalidCoordinateError,
    OutOfCoverageError,
    InvalidStudyAreaError,
    NetworkRetrievalError,
    DisconnectedNetworkError,
    DataQualityError,
)
from app.geospatial.network_adapter import OsmNetworkAdapter, NetworkResult
from app.geospatial.lighting_adapter import OsmLightingAdapter
from app.geospatial.facilities_adapter import OsmFacilityAdapter, FacilityPoint
from app.geospatial.crime_adapter import CsvCrimeAdapter, CrimeRecord
from app.geospatial.community_adapter import DatabaseCommunityAdapter


# -----------------------------------------------------------------------------
# 1. Dependency Imports Check
# -----------------------------------------------------------------------------
def test_geospatial_dependency_imports():
    """Verify that OSMnx, NetworkX, GeoPandas, and Shapely import and report valid versions."""
    import osmnx
    import networkx
    import geopandas
    import shapely

    assert hasattr(osmnx, "__version__")
    assert hasattr(networkx, "__version__")
    assert hasattr(geopandas, "__version__")
    assert hasattr(shapely, "__version__")

    assert osmnx.__version__.startswith("2.")
    assert int(networkx.__version__.split(".")[0]) >= 3


# -----------------------------------------------------------------------------
# 2. Study Area Validation Checks
# -----------------------------------------------------------------------------
def test_valid_study_area_creation():
    """Verify that a valid StudyArea constructs properly with slug and bbox properties."""
    area = StudyArea(
        name="Bengaluru Pilot Corridor",
        south=12.9200,
        west=77.5700,
        north=12.9850,
        east=77.6200
    )
    assert area.name == "Bengaluru Pilot Corridor"
    assert area.bbox == (12.9200, 77.5700, 12.9850, 77.6200)
    # OSMnx 2.x expects (left, bottom, right, top) = (west, south, east, north)
    assert area.bbox_osmnx == (77.5700, 12.9200, 77.6200, 12.9850)
    assert "bengaluru_pilot_corridor" in area.slug
    assert area.contains_point(12.9500, 77.5900) is True
    assert area.contains_point(13.5000, 78.1000) is False


def test_invalid_study_area_bounds_rejected():
    """Verify that nonsensical bounding boxes raise InvalidStudyAreaError."""
    # South >= North
    with pytest.raises(InvalidStudyAreaError, match="strictly less than North"):
        StudyArea(name="Invalid Lat", south=13.0, west=77.0, north=12.0, east=78.0)

    # West >= East
    with pytest.raises(InvalidStudyAreaError, match="strictly less than East"):
        StudyArea(name="Invalid Lon", south=12.0, west=78.0, north=13.0, east=77.0)

    # Out-of-range latitude
    with pytest.raises(InvalidStudyAreaError, match="between -90 and 90"):
        StudyArea(name="Bad Lat Range", south=-95.0, west=77.0, north=13.0, east=78.0)

    # Empty name
    with pytest.raises(InvalidStudyAreaError, match="cannot be empty"):
        StudyArea(name="", south=12.0, west=77.0, north=13.0, east=78.0)


def test_invalid_origin_destination_coordinates():
    """Verify that mathematical coordinate violations raise InvalidCoordinateError."""
    area = StudyArea(name="Test Area", south=10.0, west=70.0, north=20.0, east=80.0)

    # Latitude > 90
    with pytest.raises(InvalidCoordinateError, match="range \\[-90..90\\]"):
        area.validate_coordinate_pair(95.0, 75.0, label="Origin")

    # Longitude > 180
    with pytest.raises(InvalidCoordinateError, match="range \\[-180..180\\]"):
        area.validate_coordinate_pair(15.0, 185.0, label="Destination")

    # Non-numeric
    with pytest.raises(InvalidCoordinateError, match="must be numeric"):
        area.validate_coordinate_pair("not_a_num", 75.0, label="Origin")


def test_missing_network_coverage_out_of_bounds():
    """Verify that coordinates outside study area raise OutOfCoverageError without fabricating routes."""
    area = StudyArea(
        name="Bengaluru Pilot Corridor",
        south=12.9200,
        west=77.5700,
        north=12.9850,
        east=77.6200
    )

    # Coordinate outside study area (e.g. Hyderabad coordinates)
    with pytest.raises(OutOfCoverageError, match="outside configured study area"):
        area.validate_coordinate_pair(17.3850, 78.4867, label="Origin")


# -----------------------------------------------------------------------------
# 3. Pedestrian Network Retrieval, Caching, and Connectivity (Mocked External)
# -----------------------------------------------------------------------------
def test_network_retrieval_and_caching_mocked():
    """
    Test pedestrian network retrieval and GraphML caching using a deterministic mock graph.
    Label: Mocked external Overpass service.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        adapter = OsmNetworkAdapter(cache_dir=tmp_dir)
        area = StudyArea(name="Mock Corridor", south=12.92, west=77.58, north=12.95, east=77.60)

        # Build deterministic mock pedestrian graph
        mock_graph = nx.MultiDiGraph()
        mock_graph.graph["crs"] = "epsg:4326"
        mock_graph.add_node(1, y=12.93, x=77.59)
        mock_graph.add_node(2, y=12.94, x=77.59)
        mock_graph.add_edge(1, 2, 0, length=100.0, highway="footway", lit="yes")

        # Mock ox.graph_from_bbox to return our deterministic graph
        with patch("osmnx.graph_from_bbox", return_value=mock_graph) as mock_fetch:
            # 1. First call: fetches and caches
            res1 = adapter.get_pedestrian_network(area, force_reload=False)
            assert res1.is_cached is False
            assert res1.nodes_count == 2
            assert res1.edges_count == 1
            assert mock_fetch.call_count == 1
            assert os.path.isfile(res1.cache_path)

            # 2. Second call: loads from cache without calling Overpass
            res2 = adapter.get_pedestrian_network(area, force_reload=False)
            assert res2.is_cached is True
            assert res2.nodes_count == 2
            assert mock_fetch.call_count == 1  # Not called again!


def test_disconnected_pedestrian_network_reachability():
    """Verify that disconnected subgraphs trigger DisconnectedNetworkError."""
    adapter = OsmNetworkAdapter()

    # Disconnected graph: node 1-2 and isolated node 3
    G = nx.MultiDiGraph()
    G.add_node(1, y=12.93, x=77.58)
    G.add_node(2, y=12.94, x=77.58)
    G.add_node(3, y=12.95, x=77.59)
    G.add_edge(1, 2, 0, length=50.0)

    # Path exists 1 -> 2
    assert adapter.check_reachability(G, 1, 2) is True

    # Path does NOT exist 1 -> 3
    with pytest.raises(DisconnectedNetworkError, match="disconnected pedestrian subgraphs"):
        adapter.check_reachability(G, 1, 3)


# -----------------------------------------------------------------------------
# 4. Street Lighting Audit & Uncertainty Preservation
# -----------------------------------------------------------------------------
def test_lighting_audit_missing_tags_classified_as_unmapped():
    """
    Verify that missing lighting tags are classified as 'unmapped' uncertainty,
    NOT assumed to be unlit.
    """
    adapter = OsmLightingAdapter()
    area = StudyArea(name="Lighting Audit Area", south=12.0, west=77.0, north=13.0, east=78.0)

    G = nx.MultiDiGraph()
    G.add_node(1, y=12.1, x=77.1)
    G.add_node(2, y=12.2, x=77.1)
    G.add_node(3, y=12.3, x=77.1)
    G.add_node(4, y=12.4, x=77.1)

    # Edge 1-2: Explicitly lit
    G.add_edge(1, 2, 0, lit="yes")
    # Edge 2-3: Explicitly unlit
    G.add_edge(2, 3, 0, lit="no")
    # Edge 3-4: Missing lit tag (unmapped)
    G.add_edge(3, 4, 0, highway="residential")

    audit = adapter.audit_lighting(area, G)
    assert audit.total_edges_inspected == 3
    assert audit.explicitly_lit_edges_count == 1
    assert audit.explicitly_unlit_edges_count == 1
    assert audit.unmapped_edges_count == 1
    # Coverage is (1+1)/3 = 66.7% -> limited
    assert audit.data_state == "limited"
    assert "survey gap, NOT the physical absence of lighting" in audit.caveat


# -----------------------------------------------------------------------------
# 5. Crime Dataset Ingestion & Missing Data Honesty
# -----------------------------------------------------------------------------
def test_missing_crime_dataset_handled_honestly():
    """Verify that when no crime dataset is provided, adapter reports unconfigured without fabricating data."""
    adapter = CsvCrimeAdapter(default_file_path=None)
    result = adapter.load_crime_dataset(file_path=None)

    assert result.is_loaded is False
    assert result.record_count == 0
    assert result.spatial_precision == "unavailable"
    assert any("strictly refuses to fabricate synthetic crime records" in lim for lim in result.limitations)


def test_crime_dataset_csv_import_and_pii_rejection():
    """Verify that a valid CSV imports correctly and prohibited PII columns cause rejection."""
    adapter = CsvCrimeAdapter()

    # 1. Valid crime CSV
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
        f.write("incident_id,category,timestamp,latitude,longitude,spatial_precision\n")
        f.write("inc-01,theft,2026-05-10T20:00:00Z,12.9350,77.5850,block_level\n")
        f.write("inc-02,harassment,2026-06-12T22:30:00Z,12.9400,77.5860,block_level\n")
        valid_csv_path = f.name

    try:
        res = adapter.load_crime_dataset(valid_csv_path)
        assert res.is_loaded is True
        assert res.record_count == 2
        assert res.categories == ["harassment", "theft"]
        assert res.records[0].latitude == 12.9350
    finally:
        if os.path.exists(valid_csv_path):
            os.remove(valid_csv_path)

    # 2. Invalid CSV containing prohibited PII column (e.g. victim name)
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
        f.write("incident_id,category,timestamp,latitude,longitude,victim_name\n")
        f.write("inc-03,theft,2026-05-10T20:00:00Z,12.9350,77.5850,John Doe\n")
        pii_csv_path = f.name

    try:
        with pytest.raises(DataQualityError, match="prohibited personal identifying column"):
            adapter.load_crime_dataset(pii_csv_path)
    finally:
        if os.path.exists(pii_csv_path):
            os.remove(pii_csv_path)


# -----------------------------------------------------------------------------
# 6. Civic Facilities Retrieval (Police vs Hospitals) (Mocked External)
# -----------------------------------------------------------------------------
def test_facilities_adapter_separates_police_and_healthcare_mocked():
    """
    Verify that OsmFacilityAdapter strictly separates police stations from healthcare facilities.
    Label: Mocked external OSMnx features API.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        adapter = OsmFacilityAdapter(cache_dir=tmp_dir)
        area = StudyArea(name="Mock Facility Area", south=12.92, west=77.57, north=12.98, east=77.62)

        # Mock ox.features.features_from_bbox
        import pandas as pd
        from shapely.geometry import Point
        import geopandas as gpd

        mock_police_gdf = gpd.GeoDataFrame({
            "name": ["Jayanagar Police Station"],
            "amenity": ["police"],
            "geometry": [Point(77.5830, 12.9300)]
        }, crs="epsg:4326")

        mock_hosp_gdf = gpd.GeoDataFrame({
            "name": ["Lalbagh General Hospital"],
            "amenity": ["hospital"],
            "geometry": [Point(77.5850, 12.9450)]
        }, crs="epsg:4326")

        def mock_features_side_effect(bbox, tags):
            if "police" in tags.get("amenity", []):
                return mock_police_gdf
            return mock_hosp_gdf

        with patch("osmnx.features.features_from_bbox", side_effect=mock_features_side_effect):
            result = adapter.get_facilities(area, force_reload=True)
            assert result.police_count == 1
            assert result.hospital_count == 1
            assert result.police_stations[0].facility_type == "police"
            assert result.police_stations[0].name == "Jayanagar Police Station"
            assert result.hospitals[0].facility_type == "hospital"
            assert result.hospitals[0].name == "Lalbagh General Hospital"


# -----------------------------------------------------------------------------
# 7. Community Reports Database Audit & PII Stripping
# -----------------------------------------------------------------------------
def test_community_reports_audit_and_pii_detachment(db):
    """
    Verify that community reports from the relational database are audited,
    categorized, and stripped of all reporter personal identities.
    """
    adapter = DatabaseCommunityAdapter()
    area = StudyArea.from_settings()

    audit = adapter.audit_community_reports(db, area, only_approved=False)
    assert audit.total_reports_count >= 4
    assert audit.approved_reports_count >= 2

    # Check PII stripping on extracted incidents
    for inc in audit.incidents:
        inc_dict = inc.to_dict()
        assert "reporter_name" not in inc_dict
        assert "user_id" not in inc_dict
        assert "email" not in inc_dict
        assert "phone" not in inc_dict


# -----------------------------------------------------------------------------
# 8. API Endpoint Routing & Out-of-Coverage HTTP Rejection
# -----------------------------------------------------------------------------
def test_route_compare_endpoint_rejects_out_of_bounds(client):
    """Verify that /routes/compare rejects coordinates outside study area with 400 Bad Request."""
    # Out of study area bounds (e.g. Mumbai coordinates)
    payload = {
        "origin": "18.9220, 72.8347",
        "destination": "18.9300, 72.8400",
        "walkingMode": "pedestrian"
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 400
    assert "outside configured study area" in response.json()["detail"]


def test_route_compare_endpoint_rejects_invalid_coords(client):
    """Verify that /routes/compare rejects invalid coordinates (lat > 90) with 422."""
    payload = {
        "origin": "95.0000, 77.5833",
        "destination": "12.9500, 77.5847",
        "walkingMode": "pedestrian"
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 422
    assert "outside valid range" in response.json()["detail"]


def test_study_area_endpoints(client):
    """Verify GET /api/v1/study-area and GET /api/v1/study-area/audit."""
    # 1. Study area metadata
    res = client.get("/api/v1/study-area")
    assert res.status_code == 200
    data = res.json()
    assert "Bengaluru Pilot Corridor" in data["name"]
    assert "south" in data["bbox"]

    # 2. Study area readiness audit (label: mocked external facility network call)
    from app.geospatial.facilities_adapter import FacilityAuditResult
    mock_fac = FacilityAuditResult(
        study_area_name="Bengaluru Pilot Corridor",
        police_stations=[],
        hospitals=[],
        sources=["OpenStreetMap (Deterministic Mock)"],
        retrieved_at="2026-10-27T00:00:00Z"
    )
    with patch("app.geospatial.facilities_adapter.OsmFacilityAdapter.get_facilities", return_value=mock_fac):
        audit_res = client.get("/api/v1/study-area/audit")
        assert audit_res.status_code == 200
        audit_data = audit_res.json()
        assert "lighting" in audit_data
        assert "facilities" in audit_data
        assert "crime" in audit_data
        assert "communityReports" in audit_data

