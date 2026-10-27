from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.report import CommunityReport
from app.models.user import User
from app.models.audit import AuditLog


def test_moderator_can_approve_report(client: TestClient, moderator_headers: dict, db: Session):
    """Moderator transitions a pending report to approved."""
    rep = CommunityReport(
        id="rep-pending-mod-test",
        category="broken_lighting",
        category_label="Broken street lighting",
        location="11th Main Road",
        description="Flickering luminaire reported by community member.",
        status="pending",
        reporter_name="Citizen",
        provenance="Test"
    )
    db.add(rep)
    db.commit()

    payload = {
        "status": "approved",
        "reason": "Corroborated with municipal streetlight asset survey."
    }
    response = client.patch(f"/api/v1/admin/reports/{rep.id}", json=payload, headers=moderator_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["moderatorNotes"] == payload["reason"]


def test_moderation_audit_log_created(client: TestClient, moderator_headers: dict, db: Session):
    """Verify moderation action persists an immutable audit log record."""
    rep = CommunityReport(
        id="rep-audit-test",
        category="construction_hazard",
        category_label="Construction or pavement hazard",
        location="South End Junction",
        description="Pavement slabs dislodged by sewer pipeline excavation.",
        status="pending",
        reporter_name="Commuter",
        provenance="Test"
    )
    db.add(rep)
    db.commit()

    client.patch(
        f"/api/v1/admin/reports/{rep.id}",
        json={"status": "flagged", "reason": "Requires on-site safety barrier check."},
        headers=moderator_headers
    )

    log = db.query(AuditLog).filter(AuditLog.record.ilike("%rep-audit-test%")).first()
    assert log is not None
    assert "pending -> flagged" in log.action
    assert log.actor == "Arun Moderator"
    assert log.actor_role == "moderator"


def test_traveller_cannot_moderate(client: TestClient, traveller_headers: dict, db: Session):
    """Standard traveller receives 403 Forbidden when attempting moderation."""
    response = client.patch(
        "/api/v1/admin/reports/rep-101",
        json={"status": "approved", "reason": "Unauthorized approval attempt."},
        headers=traveller_headers
    )
    assert response.status_code == 403


def test_invalid_status_transition_rejected(client: TestClient, moderator_headers: dict, db: Session):
    """Invalid transition (e.g. rejected -> approved directly) returns 400 Bad Request."""
    rep = CommunityReport(
        id="rep-rejected-direct",
        category="other_concern",
        category_label="Other street condition",
        location="Unknown lane",
        description="Spam report previously marked as rejected.",
        status="rejected",
        reporter_name="Anon",
        provenance="Test"
    )
    db.add(rep)
    db.commit()

    response = client.patch(
        f"/api/v1/admin/reports/{rep.id}",
        json={"status": "approved", "reason": "Illegal transition attempt."},
        headers=moderator_headers
    )
    assert response.status_code == 400
    assert "Invalid status transition" in response.json()["detail"]


def test_admin_user_role_update(client: TestClient, admin_headers: dict, traveller_user: User):
    """Administrator can update user role."""
    payload = {"role": "moderator"}
    response = client.patch(f"/api/v1/admin/users/{traveller_user.id}", json=payload, headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "moderator"


def test_moderator_cannot_update_roles(client: TestClient, moderator_headers: dict, traveller_user: User):
    """Moderator cannot update user roles (Admin privilege only)."""
    response = client.patch(
        f"/api/v1/admin/users/{traveller_user.id}",
        json={"role": "administrator"},
        headers=moderator_headers
    )
    assert response.status_code == 403


def test_admin_data_sources_endpoint(client: TestClient, admin_headers: dict):
    """Administrator inspects data sources and staleness warnings."""
    response = client.get("/api/v1/admin/data-sources", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    # Check police directory has stale warning
    stale_items = [s for s in data["items"] if s["staleWarning"] is True]
    assert len(stale_items) > 0


def test_admin_audit_logs_endpoint(client: TestClient, admin_headers: dict):
    """Administrator inspects audit log trail."""
    response = client.get("/api/v1/admin/audit", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_admin_settings_get_and_patch(client: TestClient, admin_headers: dict):
    """Administrator inspects and updates system governance settings."""
    # GET settings
    get_res = client.get("/api/v1/admin/settings", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["freshnessThresholdDays"] == 30

    # PATCH settings
    patch_res = client.patch(
        "/api/v1/admin/settings",
        json={"freshnessThresholdDays": 45, "autoFlagKeywords": "harassment, assault, dark, broken, hazard, hazard_wire"},
        headers=admin_headers
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["freshnessThresholdDays"] == 45
    assert "hazard_wire" in patch_res.json()["autoFlagKeywords"]
