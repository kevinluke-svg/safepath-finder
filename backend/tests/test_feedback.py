import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.feedback import Feedback
from app.models.audit import AuditLog


def test_submit_feedback_authenticated(client: TestClient, traveller_headers: dict, traveller_user: User, db: Session):
    """Authenticated user submits feedback; user ID is linked and status is 'new'."""
    payload = {
        "category": "lighting_accuracy",
        "message": "Streetlights near 10th Main were replaced with bright LEDs yesterday. Excellent update!",
        "rating": 5
    }
    response = client.post("/api/v1/feedback", json=payload, headers=traveller_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["category"] == "lighting_accuracy"
    assert data["status"] == "new"
    assert data["isAnonymous"] is False

    # Check database persistence
    fb = db.query(Feedback).filter(Feedback.id == data["id"]).first()
    assert fb is not None
    assert fb.user_id == traveller_user.id
    assert fb.rating == 5


def test_submit_feedback_anonymous(client: TestClient, db: Session):
    """Anonymous user submits feedback; user ID is None."""
    payload = {
        "category": "safety_concern",
        "message": "Overhanging tree branches near park entrance obscure the footpath.",
        "rating": 3
    }
    response = client.post("/api/v1/feedback", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["isAnonymous"] is True

    fb = db.query(Feedback).filter(Feedback.id == data["id"]).first()
    assert fb is not None
    assert fb.user_id is None


def test_feedback_validation_failures(client: TestClient):
    """Feedback message must be at least 5 characters and category must be valid."""
    # Too short
    res1 = client.post("/api/v1/feedback", json={"category": "general", "message": "hi"})
    assert res1.status_code == 422

    # Invalid rating
    res2 = client.post("/api/v1/feedback", json={"category": "general", "message": "Valid length message", "rating": 10})
    assert res2.status_code == 422


def test_feedback_inbox_access_control(client: TestClient, traveller_headers: dict, moderator_headers: dict, admin_headers: dict):
    """Only moderators and administrators can view the feedback inbox."""
    # Traveller -> 403
    res_trav = client.get("/api/v1/admin/feedback", headers=traveller_headers)
    assert res_trav.status_code == 403

    # Moderator -> 200
    res_mod = client.get("/api/v1/admin/feedback", headers=moderator_headers)
    assert res_mod.status_code == 200
    assert "items" in res_mod.json()

    # Admin -> 200
    res_admin = client.get("/api/v1/admin/feedback", headers=admin_headers)
    assert res_admin.status_code == 200


def test_feedback_status_update_and_audit(client: TestClient, moderator_headers: dict, moderator_user: User, db: Session):
    """Moderator can triage feedback, update status, and add administrative review notes."""
    # 1. Create a feedback record directly
    fb = Feedback(
        category="app_bug",
        message="Search input resets when toggling mobile drawer.",
        status="new"
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    # 2. Update status to 'under_review' with notes
    update_payload = {
        "status": "under_review",
        "adminNotes": "Investigating state persistence bug in app.js"
    }
    res = client.patch(f"/api/v1/admin/feedback/{fb.id}", json=update_payload, headers=moderator_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "under_review"
    assert data["adminNotes"] == "Investigating state persistence bug in app.js"
    assert data["reviewedBy"] == moderator_user.name

    # 3. Verify audit log entry
    audit = db.query(AuditLog).filter(
        AuditLog.action == "Feedback Status Updated"
    ).order_by(AuditLog.timestamp.desc()).first()
    assert audit is not None
    assert fb.id in audit.record
