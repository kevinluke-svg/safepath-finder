"""
SafePath Finder — Phase 2 & Open Data Integrity Test Suite
Verifies:
1. Mapped lit (lit=yes) is classified as cartographically mapped lit, not field-verified operational.
2. Mapped unlit (lit=no) is classified as mapped unlit.
3. Missing lighting information is classified as unknown/unmapped.
4. Mapped lamp assets (highway=street_lamp) do not prove road-wide illumination.
5. An area with no crime records is NEVER classified as crime-free (zero != safe).
6. Aggregate crime data (NCRB city stats) is not assigned to arbitrary individual streets.
7. Unknown sidewalk info is not counted as confirmed sidewalk absence.
8. Route overlap is calculated from actual geometries or graph edges with documented denominators.
9. Duplicate routes are detected and clearly labeled.
10. Distinct routes are genuinely different in edge sequences.
11. Routes with insufficient evidence display an uncertainty warning.
12. Facility distance calculations use the pedestrian network where possible.
13. Dataset import failures do not corrupt existing database records.
14. Re-importing an unchanged dataset does not create duplicate records.
15. All routes strictly obey valid pedestrian-network connectivity.
"""

import pytest
import networkx as nx
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.geospatial.lighting_processor import LightingProcessor
from app.geospatial.pedestrian_infrastructure import PedestrianInfrastructureProcessor
from app.geospatial.crime_adapter import CsvCrimeAdapter, CrimeDatasetResult
from app.geospatial.facilities_adapter import OsmFacilityAdapter, FacilityPoint, FacilityAuditResult
from app.geospatial.dijkstra_router import DijkstraRouter, calculate_path_edge_overlap
from app.geospatial.segment_risk import SegmentRiskModel
from app.geospatial.study_area import StudyArea
from app.geospatial.network_adapter import OsmNetworkAdapter
from app.models.evidence import EvidenceSource, DatasetImportHistory
from app.db.seed import seed_database


# =============================================================================
# 1. LIGHTING EVIDENCE & EPISTEMOLOGICAL STANDARDS
# =============================================================================

def test_street_segment_lit_yes_classified_as_mapped_lit_not_field_verified_operational():
    """A street segment with lit=yes is classified as mapped lit, not field-verified operational."""
    processor = LightingProcessor()
    classification = processor.classify_edge_lighting({"lit": "yes"}, 1, 2)
    assert classification.lit_status == "lit"
    assert classification.data_state == "present"
    assert "field-verified operational" not in classification.notes.lower() or "not field-verified" in classification.notes.lower()
    assert any("power grid" in lim.lower() or "bulb" in lim.lower() for lim in classification.limitations)


def test_street_segment_lit_no_classified_as_mapped_unlit():
    """A segment with lit=no is classified as mapped unlit."""
    processor = LightingProcessor()
    classification = processor.classify_edge_lighting({"lit": "no"}, 1, 2)
    assert classification.lit_status == "unlit"
    assert classification.data_state == "present"
    assert "mapped as unlit" in classification.notes.lower()


def test_street_segment_no_lighting_info_classified_as_unknown():
    """A segment with no lighting information is classified as unknown/unmapped."""
    processor = LightingProcessor()
    classification = processor.classify_edge_lighting({}, 1, 2)
    assert classification.lit_status == "unmapped"
    assert classification.data_state == "missing"
    assert classification.confidence == "low"
    assert "uncertainty" in classification.notes.lower() or "unmapped" in classification.notes.lower()


def test_mapped_lamp_asset_not_counted_as_proof_of_road_wide_illumination():
    """A mapped lamp asset (highway=street_lamp) is not counted as proof of road-wide illumination."""
    processor = LightingProcessor()
    # Edge with no way lighting tag, but 1 isolated streetlamp point
    classification = processor.classify_edge_lighting({}, 1, 2, associated_lamp_count=1)
    # Missing tag should still remain unmapped / missing, NOT automatically lit with high confidence
    assert classification.lit_status == "unmapped"
    assert classification.confidence == "low"
    assert classification.data_state == "missing"


# =============================================================================
# 2. CRIME EVIDENCE & AGGREGATE STATS INTEGRITY
# =============================================================================

def test_area_with_no_crime_records_not_classified_as_crime_free():
    """An area with zero crime records is NOT classified as crime-free; uncertainty prior is preserved."""
    adapter = CsvCrimeAdapter()
    result = adapter.load_crime_dataset(None)
    assert result.is_loaded is False
    assert result.record_count == 0
    # Strict epistemic limitations must be recorded
    assert any("never be interpreted as proof that a route or area is crime-free" in lim.lower() for lim in result.limitations)

    # Risk model must apply neutral unknown prior R_unknown = 0.50, NOT 0.00
    model = SegmentRiskModel(r_unknown_prior=0.50)
    profile = model.evaluate_edge(
        edge_data={},
        edge_length_meters=200.0,
        lit_status="unmapped",
        crime_count=0,
        has_crime_dataset=False
    )
    # Effective risk is driven by R_unknown = 0.50, never 0.0
    assert profile.effective_risk >= 0.40


def test_aggregate_crime_data_not_assigned_to_arbitrary_individual_streets():
    """Aggregate NCRB city statistics are strictly contextual and not distributed across individual streets."""
    adapter = CsvCrimeAdapter()
    result = adapter.load_crime_dataset(None)
    assert result.spatial_precision in ("unavailable", "city_aggregate_only")
    assert len(result.records) == 0  # Zero point records fabricated
    if result.contextual_aggregate_stats:
        assert "categories" in result.contextual_aggregate_stats
        assert "violentCrimes" in result.contextual_aggregate_stats["categories"]
        assert "2022" in result.contextual_aggregate_stats["collectionPeriod"]


# =============================================================================
# 3. PEDESTRIAN INFRASTRUCTURE EVIDENCE
# =============================================================================

def test_unknown_sidewalk_info_not_counted_as_confirmed_sidewalk_absence():
    """Unknown sidewalk information is not counted as confirmed sidewalk absence."""
    processor = PedestrianInfrastructureProcessor()
    # Missing sidewalk tag on regular street
    classification = processor.classify_edge_infrastructure({}, 1, 2)
    assert classification.sidewalk_status == "unmapped"
    assert classification.sidewalk_status != "none"
    assert classification.data_state == "missing"

    # Confirmed absence only when explicitly tagged
    classification_absent = processor.classify_edge_infrastructure({"sidewalk": "no"}, 1, 2)
    assert classification_absent.sidewalk_status == "none"
    assert classification_absent.data_state == "present"


# =============================================================================
# 4. ROUTE OVERLAP, DEDUPLICATION & DIFFERENTIATION
# =============================================================================

def test_route_overlap_calculated_from_actual_geometries_or_graph_edges():
    """Route overlap is calculated from shared edge lengths with documented denominators."""
    g = nx.MultiDiGraph()
    # Path 1: 1 -> 2 -> 3 (lengths 100 + 100 = 200m)
    g.add_edge(1, 2, 0, length=100.0)
    g.add_edge(2, 3, 0, length=100.0)
    # Path 2: 1 -> 2 -> 4 (shares edge (1, 2), disjoint edge (2, 4) of length 100m)
    g.add_edge(2, 4, 0, length=100.0)

    path1 = [1, 2, 3]
    path2 = [1, 2, 4]

    # Shared edge length = 100m
    # Jaccard union denominator = 300m -> overlap = 100 / 300 = 0.333
    overlap_union = calculate_path_edge_overlap(path1, path2, g, denominator="union")
    assert round(overlap_union, 2) == 0.33

    # Candidate denominator = 200m -> overlap = 100 / 200 = 0.50
    overlap_cand = calculate_path_edge_overlap(path1, path2, g, denominator="candidate")
    assert round(overlap_cand, 2) == 0.50

    # Identical paths: overlap = 1.0
    assert calculate_path_edge_overlap(path1, path1, g) == 1.0


def test_duplicate_routes_detected_and_labeled():
    """Duplicate route geometry is detected and clearly marked as identical with rationale."""
    g = nx.MultiDiGraph()
    g.add_node(1, y=12.93, x=77.58)
    g.add_node(2, y=12.94, x=77.58)
    g.add_edge(1, 2, 0, length=100.0, highway="residential")

    router = DijkstraRouter(g, SegmentRiskModel())
    routes = router.compute_all_routes(12.93, 77.58, 12.94, 77.58, include_alternatives=False)

    fastest = next(r for r in routes if r.category == "fastest")
    balanced = next(r for r in routes if r.category == "balanced")
    assert fastest.overlap_with_fastest == 1.0
    assert balanced.is_identical_to_fastest is True
    assert balanced.overlap_with_fastest == 1.0
    assert "Optimal under both" in (balanced.identical_notes or "")


def test_distinct_routes_genuinely_different_in_edge_sequences():
    """Distinct route alternatives have genuinely different edge sequences and overlap <= threshold."""
    # Build a diamond network with two parallel corridors
    g = nx.MultiDiGraph()
    # Node coordinates
    g.add_node(1, y=12.930, x=77.580)
    g.add_node(2, y=12.935, x=77.575)  # Left fork
    g.add_node(3, y=12.935, x=77.585)  # Right fork
    g.add_node(4, y=12.940, x=77.580)

    # Left corridor (faster, unlit)
    g.add_edge(1, 2, 0, length=100.0, highway="residential", lit="no")
    g.add_edge(2, 4, 0, length=100.0, highway="residential", lit="no")

    # Right corridor (slightly longer, lit)
    g.add_edge(1, 3, 0, length=110.0, highway="residential", lit="yes")
    g.add_edge(3, 4, 0, length=110.0, highway="residential", lit="yes")

    router = DijkstraRouter(g, SegmentRiskModel(lambda_safety=2.0))
    routes = router.compute_all_routes(12.930, 77.580, 12.940, 77.580, include_alternatives=True)

    fastest = next(r for r in routes if r.category == "fastest")
    safety = next(r for r in routes if r.category == "safety_prioritized")

    # The fastest route goes via node 2, safety-prioritized goes via node 3
    assert fastest.node_path == [1, 2, 4]
    assert safety.node_path == [1, 3, 4]
    # Edge overlap between the two distinct corridors is 0%
    overlap = calculate_path_edge_overlap(fastest.node_path, safety.node_path, g, denominator="candidate")
    assert overlap == 0.0


def test_route_with_insufficient_evidence_displays_uncertainty_warning(client: TestClient):
    """A route with insufficient data coverage displays an uncertainty warning and is flagged honestly."""
    payload = {
        "origin": "Jayanagar 4th Block, Bengaluru",
        "destination": "Lalbagh West Gate, Bengaluru",
        "walkingMode": "pedestrian"
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    for route in data["routes"]:
        cov_pct = route["evidenceSummary"]["coveragePercentage"]
        if cov_pct < 30 or route["evidenceSummary"]["coverage"] == "insufficient":
            assert route["hasInsufficientEvidence"] is True or "insufficient" in route["evidenceSummary"]["coverage"]


# =============================================================================
# 5. CIVIC ASSISTANCE & PEDESTRIAN NETWORK DISTANCE
# =============================================================================

def test_facility_distance_calculations_use_pedestrian_network_where_possible():
    """Civic safety facilities calculate distance via the pedestrian network when connected."""
    g = nx.MultiDiGraph()
    # Simple straight corridor: 1 -> 2 -> 3 (total 500m)
    g.add_node(1, y=12.9250, x=77.5800)
    g.add_node(2, y=12.9350, x=77.5800)
    g.add_node(3, y=12.9450, x=77.5800)
    g.add_edge(1, 2, 0, length=250.0, highway="residential")
    g.add_edge(2, 3, 0, length=250.0, highway="residential")

    p1 = FacilityPoint(
        id="pol-test",
        facility_type="police",
        name="Ashoka Police Post",
        latitude=12.9351,
        longitude=77.5801,
        source="OpenStreetMap",
        confidence="verified_spatial_point",
        is_assistance=True
    )
    fac_result = FacilityAuditResult(
        study_area_name="test",
        police_stations=[p1],
        hospitals=[],
        sources=["OpenStreetMap"],
        retrieved_at="2026-11-12T00:00:00Z"
    )

    router = DijkstraRouter(g, facilities_result=fac_result)
    routes = router.compute_all_routes(12.9250, 77.5800, 12.9450, 77.5800)
    route = routes[0]
    places = route.nearby_places
    assert len(places) >= 1
    place = places[0]
    assert place["name"] == "Ashoka Police Post"
    assert place["distanceMeters"] <= 100.0


# =============================================================================
# 6. DATABASE ROBUSTNESS & IDEMPOTENCE
# =============================================================================

def test_reimporting_unchanged_dataset_does_not_create_duplicate_records(db: Session):
    """Re-seeding or re-importing unchanged dataset registry does not create duplicate records."""
    count_before = db.query(EvidenceSource).count()
    seed_database(db)
    count_after = db.query(EvidenceSource).count()
    assert count_before == count_after

    sources = db.query(EvidenceSource).all()
    source_ids = [s.id for s in sources]
    assert len(source_ids) == len(set(source_ids))


def test_dataset_import_failures_do_not_corrupt_existing_records(db: Session):
    """Database transaction rollback on import failure preserves existing registry."""
    initial_src = EvidenceSource(
        id="src-test-preserve-1",
        name="Preserved Test Dataset",
        type="Open Data",
        coverage="Bengaluru Test Corridor",
        refresh_frequency="Monthly",
        last_ingested=datetime.now(timezone.utc),
        source_organisation="SafePath Test Org",
        licence="ODbL 1.0",
        status="active"
    )
    db.add(initial_src)
    db.commit()

    count_initial = db.query(EvidenceSource).filter(EvidenceSource.id == "src-test-preserve-1").count()
    assert count_initial == 1

    # Test that savepoint rollback on constraint failure preserves initial record
    try:
        with db.begin_nested():
            bad_source = EvidenceSource(
                id="src-test-preserve-2",
                name="Corrupted Dataset Entry",
                type=None  # Violates NOT NULL constraint
            )
            db.add(bad_source)
            db.flush()
    except Exception:
        pass  # Nested savepoint rolled back cleanly

    count_after_failure = db.query(EvidenceSource).filter(EvidenceSource.id == "src-test-preserve-1").count()
    assert count_after_failure == 1

    # Clean up test record
    rec = db.query(EvidenceSource).filter(EvidenceSource.id == "src-test-preserve-1").first()
    if rec:
        db.delete(rec)
        db.commit()


# =============================================================================
# 7. PEDESTRIAN NETWORK CONNECTIVITY GUARANTEE
# =============================================================================

def test_all_routes_obey_valid_pedestrian_network_connectivity():
    """All generated routes strictly traverse valid contiguous directed edges in the network graph."""
    study_area = StudyArea.from_settings()
    net = OsmNetworkAdapter().get_pedestrian_network(study_area)
    router = DijkstraRouter(net.graph, SegmentRiskModel())

    # Jayanagar 4th Block (12.9290, 77.5830) to South End Circle (12.9360, 77.5800)
    routes = router.compute_all_routes(12.9290, 77.5830, 12.9360, 77.5800, include_alternatives=True)
    assert len(routes) >= 3

    for r in routes:
        path = r.node_path
        assert len(path) >= 2
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            assert net.graph.has_edge(u, v), f"Edge ({u}, {v}) in route '{r.name}' does not exist in pedestrian graph!"
