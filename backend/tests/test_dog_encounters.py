"""
SafePath Finder — Comprehensive Street Dog Encounter Evidence & Community Reporting Tests
Tests:
- Submitting each dog-report category (dog_sighting, dog_group, dog_aggressive, dog_bite)
- Coordinate and date validation (lat/lon bounds, future encounter dates)
- Duplicate-report spatial-temporal clustering (30m / 24h)
- Report moderation (pending -> approved, pending -> rejected, auto-flagging of dog bites)
- Report withdrawal and correction with strict ownership authorization (anti-IDOR)
- Privacy protections (zero reporter PII in public endpoints)
- Segment risk evaluation (ordinary sighting != dangerous, aggressive encounter penalization)
- Recency decay weighting
- Deduplication across multiple route edges
- Route comparison API integration with dogEncounterSummary
- Data readiness audit endpoint
All synthetic dog fixtures are strictly isolated to these automated tests.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import status
from sqlalchemy.orm import Session
import networkx as nx

from app.models.report import CommunityReport
from app.models.user import User
from app.geospatial.segment_risk import SegmentRiskModel
from app.geospatial.community_processor import CommunityProcessor
from app.geospatial.dijkstra_router import DijkstraRouter
from app.geospatial.study_area import StudyArea


# -----------------------------------------------------------------------------
# 1. Submission & Category Tests
# -----------------------------------------------------------------------------
def test_submit_each_dog_report_category(client, traveller_headers):
    """Test submitting each of the 4 dog encounter categories."""
    categories = [
        ("dog_sighting", "Calm indie dog resting near park gate", 1, False),
        ("dog_group", "Pack of 4 stray dogs near commercial bins", 4, False),
        ("dog_aggressive", "Two dogs barked and chased bicycle commuter", 2, True),
        ("dog_bite", "Pedestrian bitten on calf near alleyway intersection", 1, True),
    ]

    for cat, desc, count, is_aggr in categories:
        payload = {
            "category": cat,
            "location": "10th Main Road near 28th Cross, Jayanagar",
            "description": desc,
            "latitude": 12.9290,
            "longitude": 77.5831,
            "encounterTime": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "dogCount": count,
            "isAggressive": is_aggr,
            "anonymous": True
        }
        res = client.post("/api/v1/reports", json=payload, headers=traveller_headers)
        assert res.status_code == status.HTTP_201_CREATED, f"Failed for {cat}: {res.text}"
        data = res.json()
        assert data["category"] == cat
        assert data["dogCount"] == count
        assert data["isAggressive"] is is_aggr

        # Dog bites must be automatically prioritized with "flagged" moderation status
        if cat == "dog_bite":
            assert data["status"] == "flagged"
            assert "flagged" in (data.get("moderatorNotes") or "").lower()
        else:
            assert data["status"] == "pending"


# -----------------------------------------------------------------------------
# 2. Coordinate & Input Validation Tests
# -----------------------------------------------------------------------------
def test_coordinate_and_date_validation(client, traveller_headers):
    """Ensure invalid coordinates, out-of-range bounds, and future encounter dates fail validation."""
    # Invalid latitude (> 90)
    res = client.post("/api/v1/reports", json={
        "category": "dog_sighting",
        "location": "Out of bounds",
        "description": "Observed dog in invalid latitude coordinate location.",
        "latitude": 95.0,
        "longitude": 77.5831
    }, headers=traveller_headers)
    assert res.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Invalid longitude (< -180)
    res = client.post("/api/v1/reports", json={
        "category": "dog_sighting",
        "location": "Out of bounds",
        "description": "Observed dog in invalid longitude coordinate location.",
        "latitude": 12.9350,
        "longitude": -195.0
    }, headers=traveller_headers)
    assert res.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Future encounter date
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    res = client.post("/api/v1/reports", json={
        "category": "dog_sighting",
        "location": "Future location",
        "description": "Encounter claim set in future date.",
        "latitude": 12.9350,
        "longitude": 77.5830,
        "encounterTime": future_time
    }, headers=traveller_headers)
    assert res.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)
    assert "future" in res.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 3. Duplicate Report Handling (Clustering)
# -----------------------------------------------------------------------------
def test_duplicate_report_clustering(db: Session):
    """Verify that multiple reports within 30m and 24h are flagged as potential duplicates."""
    base_time = datetime(2026, 10, 28, 10, 0, 0, tzinfo=timezone.utc)

    rep1 = CommunityReport(
        id="rep-syn-01",
        category="dog_sighting",
        category_label="Dog sighting",
        location="10th Main Road",
        description="Dog sighting report 1",
        latitude=12.93500,
        longitude=77.58300,
        created_at=base_time,
        encounter_time=base_time,
        dog_count=1,
        is_aggressive=False,
        status="approved",
        provenance="Isolated Synthetic Fixture",
        reporter_name="Anonymous",
        corroborations=1
    )
    rep2 = CommunityReport(
        id="rep-syn-02",
        category="dog_sighting",
        category_label="Dog sighting",
        location="10th Main Road near pole",
        description="Dog sighting report 2 (close by and 1h later)",
        latitude=12.93508,
        longitude=77.58305,
        created_at=base_time + timedelta(hours=1),
        encounter_time=base_time + timedelta(hours=1),
        dog_count=1,
        is_aggressive=False,
        status="approved",
        provenance="Isolated Synthetic Fixture",
        reporter_name="Anonymous",
        corroborations=1
    )
    rep3 = CommunityReport(
        id="rep-syn-03",
        category="dog_aggressive",
        category_label="Aggressive dog encounter",
        location="Lalbagh Road 400m away",
        description="Aggressive dog encounter far away",
        latitude=12.93850,
        longitude=77.58600,
        created_at=base_time + timedelta(hours=2),
        encounter_time=base_time + timedelta(hours=2),
        dog_count=2,
        is_aggressive=True,
        status="approved",
        provenance="Isolated Synthetic Fixture",
        reporter_name="Anonymous",
        corroborations=1
    )
    db.add_all([rep1, rep2, rep3])
    db.flush()

    processor = CommunityProcessor()
    study_area = StudyArea.from_settings()
    processed_list, _ = processor.process_community_reports(db, study_area)

    p1 = next(p for p in processed_list if p.report_id == "rep-syn-01")
    p2 = next(p for p in processed_list if p.report_id == "rep-syn-02")
    p3 = next(p for p in processed_list if p.report_id == "rep-syn-03")

    assert p1.is_duplicate is False
    assert p2.is_duplicate is True  # flagged as duplicate of rep-syn-01
    assert p3.is_duplicate is False # distinct distant location


# -----------------------------------------------------------------------------
# 4. Report Moderation Lifecycle
# -----------------------------------------------------------------------------
def test_report_moderation_lifecycle(client, traveller_headers, moderator_headers):
    """Test 4-state moderation pipeline: pending -> approved / rejected / flagged."""
    # Submit report
    create_res = client.post("/api/v1/reports", json={
        "category": "dog_group",
        "location": "South End Circle near Metro",
        "description": "Three dogs resting peacefully under the bridge shelter.",
        "latitude": 12.9330,
        "longitude": 77.5832,
        "dogCount": 3,
        "isAggressive": False
    }, headers=traveller_headers)
    assert create_res.status_code == status.HTTP_201_CREATED
    report_id = create_res.json()["id"]
    assert create_res.json()["status"] == "pending"

    # Moderator approves report
    patch_res = client.patch(
        f"/api/v1/admin/reports/{report_id}",
        json={"status": "approved", "reason": "Corroborated by street CCTV footage review"},
        headers=moderator_headers
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["status"] == "approved"

    # Verify report appears in public approved feed
    public_res = client.get("/api/v1/reports?category=dog_group&status=approved")
    assert public_res.status_code == status.HTTP_200_OK
    items = public_res.json().get("items", [])
    assert any(r["id"] == report_id for r in items)


# -----------------------------------------------------------------------------
# 5. User Report Correction & Withdrawal (Strict Ownership / Anti-IDOR)
# -----------------------------------------------------------------------------
def test_report_correction_and_withdrawal_ownership(client, traveller_headers, other_traveller_headers):
    """Ensure users can correct and withdraw their own reports, but CANNOT modify another user's reports."""
    # User 1 submits a report
    sub_res = client.post("/api/v1/reports", json={
        "category": "dog_sighting",
        "location": "Jayanagar 4th Block Complex",
        "description": "Brown stray dog sleeping on pavement near entrance.",
        "latitude": 12.9257,
        "longitude": 77.5833,
        "dogCount": 1
    }, headers=traveller_headers)
    report_id = sub_res.json()["id"]

    # User 2 tries to edit User 1's report -> 403 Forbidden
    idor_edit = client.put(f"/api/v1/reports/{report_id}", json={
        "description": "Maliciously modified description by non-owner."
    }, headers=other_traveller_headers)
    assert idor_edit.status_code == status.HTTP_403_FORBIDDEN

    # User 2 tries to withdraw User 1's report -> 403 Forbidden
    idor_delete = client.delete(f"/api/v1/reports/{report_id}", headers=other_traveller_headers)
    assert idor_delete.status_code == status.HTTP_403_FORBIDDEN

    # User 1 successfully corrects their own report
    legit_edit = client.put(f"/api/v1/reports/{report_id}", json={
        "description": "Corrected: Brown stray dog with green collar resting near entrance.",
        "dogCount": 2
    }, headers=traveller_headers)
    assert legit_edit.status_code == status.HTTP_200_OK
    assert legit_edit.json()["dogCount"] == 2
    assert "green collar" in legit_edit.json()["description"]

    # User 1 successfully withdraws their report
    legit_withdraw = client.delete(f"/api/v1/reports/{report_id}", headers=traveller_headers)
    assert legit_withdraw.status_code == status.HTTP_200_OK
    assert legit_withdraw.json()["status"] == "rejected"
    assert "withdrawn" in legit_withdraw.json()["moderatorNotes"].lower()


# -----------------------------------------------------------------------------
# 6. Privacy & PII Protection
# -----------------------------------------------------------------------------
def test_privacy_protections_in_public_reports(client, traveller_headers):
    """Ensure public report endpoints never expose reporter IDs, names, emails, or phone numbers."""
    # Submit report
    client.post("/api/v1/reports", json={
        "category": "dog_sighting",
        "location": "Madhavan Park Perimeter",
        "description": "Single friendly dog near children play zone fence.",
        "latitude": 12.9370,
        "longitude": 77.5860,
        "anonymous": False  # Even if anonymous=False, public API must not expose identity
    }, headers=traveller_headers)

    res = client.get("/api/v1/reports")
    assert res.status_code == status.HTTP_200_OK
    reports = res.json().get("items", [])
    assert len(reports) > 0

    for rep in reports:
        assert "userId" not in rep
        assert "user_id" not in rep
        assert "email" not in rep
        assert "phone" not in rep
        assert "ipAddress" not in rep
        assert "ip_address" not in rep
        assert "accountDetails" not in rep


# -----------------------------------------------------------------------------
# 7. Segment Risk: Ordinary Sighting vs Aggressive Encounter
# -----------------------------------------------------------------------------
def test_ordinary_sighting_does_not_inflate_risk():
    """
    Epistemological core test:
    An ordinary dog sighting must NOT automatically classify a street as dangerous.
    D_e for ordinary sighting is 0.05, which is LESS than the unobserved prior R_unknown (0.50).
    In contrast, aggressive encounters (D_e = 0.65) and bites (D_e = 0.95) legitimately increase risk.
    """
    model = SegmentRiskModel(weight_dog=0.10)
    now = datetime.now(timezone.utc)

    # Synthetic Report Fixtures (labeled as synthetic)
    class SyntheticReportFixture:
        def __init__(self, category, is_aggressive, age_days=1):
            self.category = category
            self.is_aggressive = is_aggressive
            self.encounter_time = now - timedelta(days=age_days)
            self.status = "approved"

    sighting_fixture = [SyntheticReportFixture("dog_sighting", False)]
    aggressive_fixture = [SyntheticReportFixture("dog_aggressive", True)]
    bite_fixture = [SyntheticReportFixture("dog_bite", True)]

    # Edge with no dog observations -> Q_dog = 0.0, uncertainty preserved
    profile_none = model.evaluate_edge(
        edge_data={"name": "Test Way"},
        edge_length_meters=100.0,
        lit_status="yes",
        dog_reports=[],
        dog_incidents_count=0
    )
    assert profile_none.dog_coverage == 0.0
    assert profile_none.dog_indicator == model.r_unknown_prior  # 0.50 prior

    # Edge with ordinary calm dog sighting -> D_e = 0.05 (very low concern)
    profile_sighting = model.evaluate_edge(
        edge_data={"name": "Test Way"},
        edge_length_meters=100.0,
        lit_status="yes",
        dog_reports=sighting_fixture,
        dog_incidents_count=1
    )
    assert profile_sighting.dog_coverage == 1.0
    assert profile_sighting.dog_indicator == 0.05
    # The effective risk of a lit street with a calm dog sighting is LOWER than unobserved!
    assert profile_sighting.effective_risk < profile_none.effective_risk

    # Edge with aggressive encounter -> D_e = 0.65
    profile_aggressive = model.evaluate_edge(
        edge_data={"name": "Test Way"},
        edge_length_meters=100.0,
        lit_status="yes",
        dog_reports=aggressive_fixture,
        dog_incidents_count=1
    )
    assert profile_aggressive.dog_indicator == 0.65
    assert profile_aggressive.cost_safety > profile_sighting.cost_safety

    # Edge with bite incident -> D_e = 0.95
    profile_bite = model.evaluate_edge(
        edge_data={"name": "Test Way"},
        edge_length_meters=100.0,
        lit_status="yes",
        dog_reports=bite_fixture,
        dog_incidents_count=1
    )
    assert profile_bite.dog_indicator == 0.95
    assert profile_bite.cost_safety > profile_aggressive.cost_safety


# -----------------------------------------------------------------------------
# 8. Recency Decay Weighting
# -----------------------------------------------------------------------------
def test_dog_evidence_recency_decay():
    """Verify that older dog reports receive lower recency weights."""
    model = SegmentRiskModel(weight_dog=0.10)
    now = datetime.now(timezone.utc)

    class SyntheticReportFixture:
        def __init__(self, age_days):
            self.category = "dog_aggressive"
            self.is_aggressive = True
            self.encounter_time = now - timedelta(days=age_days)
            self.status = "approved"

    recent_profile = model.evaluate_edge(
        edge_data={"name": "Recent Edge"},
        edge_length_meters=100.0,
        dog_reports=[SyntheticReportFixture(age_days=3)],
        dog_incidents_count=1
    )
    old_profile = model.evaluate_edge(
        edge_data={"name": "Old Edge"},
        edge_length_meters=100.0,
        dog_reports=[SyntheticReportFixture(age_days=120)],
        dog_incidents_count=1
    )

    # 3 days old gets 1.0 multiplier -> 0.65
    assert recent_profile.dog_indicator == 0.65
    # 120 days old gets 0.10 multiplier -> 0.65 * 0.10 = 0.065
    assert old_profile.dog_indicator == 0.065
    assert recent_profile.cost_safety > old_profile.cost_safety


# -----------------------------------------------------------------------------
# 9. Router Corridor Deduplication & Dog Summary
# -----------------------------------------------------------------------------
def test_router_corridor_deduplication():
    """Verify that a single dog report near multiple route edges is counted only ONCE in the summary."""
    G = nx.MultiDiGraph()
    # 3 collinear nodes forming 2 consecutive 100m edges
    G.add_node(1, y=12.9300, x=77.5800)
    G.add_node(2, y=12.9309, x=77.5800)
    G.add_node(3, y=12.9318, x=77.5800)
    G.add_edge(1, 2, 0, length=100.0, lit="yes")
    G.add_edge(2, 3, 0, length=100.0, lit="yes")

    # Single synthetic dog report located exactly at the junction node 2
    class SyntheticReport:
        def __init__(self):
            self.id = "rep-syn-shared"
            self.category = "dog_aggressive"
            self.status = "approved"
            self.latitude = 12.9309
            self.longitude = 77.5800
            self.encounter_time = datetime.now(timezone.utc) - timedelta(days=2)

    shared_rep = SyntheticReport()
    router = DijkstraRouter(graph=G, community_reports=[shared_rep])

    routes = router.compute_all_routes(
        origin_lat=12.9300,
        origin_lon=77.5800,
        dest_lat=12.9318,
        dest_lon=77.5800
    )
    assert len(routes) > 0
    route = routes[0]

    dog_summary = route.dog_encounter_summary
    assert dog_summary is not None
    # Deduplication check: report is counted exactly ONCE, not twice!
    assert dog_summary["totalReportsCount"] == 1
    assert dog_summary["aggressiveCount"] == 1
    assert dog_summary["sightingCount"] == 0
    assert dog_summary["biteCount"] == 0
    assert dog_summary["freshestReportDays"] == 2


# -----------------------------------------------------------------------------
# 10. Route Comparison API & Schema Integration
# -----------------------------------------------------------------------------
def test_routes_compare_api_includes_dog_summary(client, db):
    """Verify that POST /api/v1/routes/compare returns dogEncounterSummary on all route alternatives."""
    # Ensure a synthetic approved dog report exists in database near pilot corridor
    syn_report = CommunityReport(
        id="rep-syn-corridor-01",
        category="dog_sighting",
        category_label="Dog sighting (calm / informational)",
        location="Near Lalbagh West Gate",
        description="Synthetic test report: calm street dog resting near sidewalk.",
        latitude=12.9460,
        longitude=77.5844,
        encounter_time=datetime.now(timezone.utc) - timedelta(days=5),
        dog_count=1,
        is_aggressive=False,
        status="approved",
        corroborations=2,
        provenance="Isolated Synthetic Test Fixture"
    )
    db.add(syn_report)
    db.flush()

    payload = {
        "origin": "Jayanagar 4th Block",
        "destination": "Lalbagh West Gate",
        "preferences": {
            "weightDog": 0.15,
            "lambdaSafety": 1.4
        }
    }
    res = client.post("/api/v1/routes/compare", json=payload)
    assert res.status_code == status.HTTP_200_OK, res.text
    data = res.json()
    assert "routes" in data
    assert len(data["routes"]) > 0

    for alt in data["routes"]:
        assert "dogEncounterSummary" in alt
        d_sum = alt["dogEncounterSummary"]
        assert d_sum is not None
        assert "totalReportsCount" in d_sum
        assert "sightingCount" in d_sum
        assert "corridorMeters" in d_sum
        assert "explanation" in d_sum
        assert "guidance" in d_sum
        assert isinstance(d_sum["guidance"], list)


# -----------------------------------------------------------------------------
# 11. Study Area Data Readiness Audit Endpoint
# -----------------------------------------------------------------------------
def test_data_readiness_audit_endpoint(client):
    """Verify that GET /api/v1/study-area/audit reports dog encounters data-readiness."""
    res = client.get("/api/v1/study-area/audit")
    assert res.status_code == status.HTTP_200_OK
    audit = res.json()
    assert "dogEncounters" in audit
    dog_audit = audit["dogEncounters"]
    assert dog_audit["externalLiveFeedAvailable"] is False
    assert "BBMP" in dog_audit["externalLiveFeedNotes"]
    assert "categories" in dog_audit
    assert "dog_sighting" in dog_audit["categories"]
    assert "dog_bite" in dog_audit["categories"]
    assert "epistemologicalPolicy" in dog_audit
