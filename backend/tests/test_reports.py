from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.report import CommunityReport
from app.models.user import User


def test_submit_report_authenticated(client: TestClient, traveller_headers: dict, traveller_user: User):
    """Authenticated user submits an observation."""
    payload = {
        "category": "broken_lighting",
        "location": "9th Main Road near Corner House",
        "description": "Two streetlight fixtures are unlit, causing low visibility on the footway.",
        "anonymous": False,
        "latitude": 12.9280,
        "longitude": 77.5840
    }
    response = client.post("/api/v1/reports", json=payload, headers=traveller_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("rep-")
    assert data["category"] == "broken_lighting"
    assert data["categoryLabel"] == "Broken street lighting"
    assert data["reporterName"] == traveller_user.name
    assert "Reported by Priya Sharma" in data["provenance"]


def test_submit_report_anonymous(client: TestClient):
    """Anonymous user submits an observation without auth."""
    payload = {
        "category": "blocked_footpath",
        "location": "Near Lalbagh West Gate",
        "description": "Fallen tree branch completely blocks the pedestrian footpath.",
        "anonymous": True
    }
    response = client.post("/api/v1/reports", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["reporterName"] == "Anonymous"
    assert "Anonymous" in data["provenance"]


def test_submit_report_validation_failures(client: TestClient, traveller_headers: dict):
    """Reject invalid reports (description too short, invalid category)."""
    # Description too short (< 10 chars)
    res1 = client.post("/api/v1/reports", json={
        "category": "broken_lighting",
        "location": "Main Road",
        "description": "Too short"
    }, headers=traveller_headers)
    assert res1.status_code == 422

    # Invalid category
    res2 = client.post("/api/v1/reports", json={
        "category": "unsupported_category",
        "location": "Main Road",
        "description": "Valid length description for testing validation."
    }, headers=traveller_headers)
    assert res2.status_code == 422


def test_auto_flag_keyword_trigger(client: TestClient, traveller_headers: dict):
    """Submissions containing auto-flag keywords transition automatically to flagged state."""
    payload = {
        "category": "other_concern",
        "location": "Alleyway near bus terminus",
        "description": "Report of serious harassment observed after dark in this unlit section."
    }
    response = client.post("/api/v1/reports", json=payload, headers=traveller_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "flagged"
    assert "Automatically flagged" in data["moderatorNotes"]


def test_public_reports_listing(client: TestClient, db: Session):
    """Public listing retrieves reports and supports filtering."""
    # Add a rejected report in database
    rej = CommunityReport(
        id="rep-rejected-test",
        category="other_concern",
        category_label="Other street condition",
        location="Spam location",
        description="Spam report description that should be hidden from public feed.",
        status="rejected",
        reporter_name="Spammer",
        provenance="Test"
    )
    db.add(rej)
    db.commit()

    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    # Ensure rejected reports are excluded
    assert not any(r["id"] == "rep-rejected-test" for r in data["items"])


def test_my_reports_isolation(
    client: TestClient,
    traveller_headers: dict,
    traveller_user: User,
    other_traveller_headers: dict,
    other_traveller_user: User,
    db: Session
):
    """Ensure GET /api/v1/reports/mine returns only the caller's reports."""
    rep_traveller = CommunityReport(
        id="rep-user1",
        category="broken_lighting",
        category_label="Broken street lighting",
        location="User 1 Street",
        description="Description belonging to user 1 for isolation test.",
        status="pending",
        reporter_id=traveller_user.id,
        reporter_name=traveller_user.name,
        provenance="User 1"
    )
    rep_other = CommunityReport(
        id="rep-user2",
        category="blocked_footpath",
        category_label="Blocked footpath",
        location="User 2 Street",
        description="Description belonging to user 2 for isolation test.",
        status="pending",
        reporter_id=other_traveller_user.id,
        reporter_name=other_traveller_user.name,
        provenance="User 2"
    )
    db.add_all([rep_traveller, rep_other])
    db.commit()

    res1 = client.get("/api/v1/reports/mine", headers=traveller_headers)
    assert res1.status_code == 200
    ids1 = [r["id"] for r in res1.json()]
    assert "rep-user1" in ids1
    assert "rep-user2" not in ids1

    res2 = client.get("/api/v1/reports/mine", headers=other_traveller_headers)
    assert res2.status_code == 200
    ids2 = [r["id"] for r in res2.json()]
    assert "rep-user2" in ids2
    assert "rep-user1" not in ids2
