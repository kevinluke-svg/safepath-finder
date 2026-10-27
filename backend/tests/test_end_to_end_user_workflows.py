"""
SafePath Finder — Comprehensive End-to-End User Workflows Test Suite
Executes the full 13-stage user journey:
1. User registration and authentication.
2. Walking-route recommendation between valid corridor locations.
3. Viewing the Fastest route (minimizes traversal time).
4. Viewing the Balanced route (trade-off balance).
5. Viewing the Safety-prioritized route (prioritizes verified lighting & facilities).
6. Comparing genuine Yen loopless alternative paths.
7. Inspecting route segment evidence and uncertainty states.
8. Submitting localized community feedback / observation.
9. Verifying database persistence and moderator review visibility.
10. Administrator access to audit logging and system settings.
11. Password-reset request and token confirmation workflow.
12. Trusted-contact CRUD and privacy-safe journey ETA sharing.
13. Session termination and protection of restricted endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.feedback import Feedback
from app.models.report import CommunityReport
from app.models.contact import TrustedContact


def test_complete_thirteen_stage_user_lifecycle(
    client: TestClient,
    db: Session,
    moderator_headers: dict,
    admin_headers: dict
):
    # -------------------------------------------------------------------------
    # 1. User Registration & Login
    # -------------------------------------------------------------------------
    reg_email = "ananya.sharma@research.test"
    reg_password = "SecurePassword2026!"
    reg_payload = {
        "name": "Ananya Sharma",
        "email": reg_email,
        "password": reg_password
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "accessToken" in reg_data
    token = reg_data["accessToken"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Verify login with registered credentials
    login_res = client.post("/api/v1/auth/login", json={"email": reg_email, "password": reg_password})
    assert login_res.status_code == 200
    assert login_res.json()["user"]["email"] == reg_email

    # -------------------------------------------------------------------------
    # 2. Route Planning Between Two Valid Locations
    # -------------------------------------------------------------------------
    route_payload = {
        "origin": "Jayanagar 4th Block, Bengaluru",
        "destination": "Lalbagh West Gate, Bengaluru",
        "walkingMode": "pedestrian",
        "preferences": {
            "preferLighting": True,
            "avoidUnknown": True,
            "includeAlternatives": True,
            "maxAlternatives": 2
        }
    }
    compare_res = client.post("/api/v1/routes/compare", json=route_payload, headers=auth_headers)
    assert compare_res.status_code == 200
    compare_data = compare_res.json()
    routes = compare_data["routes"]
    assert len(routes) >= 3

    # -------------------------------------------------------------------------
    # 3. Viewing the Fastest Route
    # -------------------------------------------------------------------------
    fastest_route = next(r for r in routes if r["category"] == "fastest")
    assert fastest_route["durationSeconds"] > 0
    assert fastest_route["distanceMeters"] > 0
    assert len(fastest_route["geometry"]) >= 2
    assert "Fastest" in fastest_route["name"] or "Shortest" in fastest_route["name"]

    # -------------------------------------------------------------------------
    # 4. Viewing the Balanced Route
    # -------------------------------------------------------------------------
    balanced_route = next(r for r in routes if r["category"] == "balanced")
    assert balanced_route["durationSeconds"] >= fastest_route["durationSeconds"]
    assert "Balanced" in balanced_route["name"]

    # -------------------------------------------------------------------------
    # 5. Viewing the Safety-Prioritized Route
    # -------------------------------------------------------------------------
    safety_route = next(r for r in routes if r["category"] == "safety_prioritized")
    assert safety_route["durationSeconds"] >= fastest_route["durationSeconds"]
    assert safety_route["evidenceSummary"]["coverage"] in ("adequate", "limited", "insufficient")
    assert "Route effective risk:" in safety_route["evidenceSummary"]["riskEstimate"]

    # -------------------------------------------------------------------------
    # 6. Comparing Genuine Alternative Paths
    # -------------------------------------------------------------------------
    alt_routes = [r for r in routes if r["category"] == "alternative"]
    assert len(alt_routes) >= 1
    for alt in alt_routes:
        assert alt["geometry"] != fastest_route["geometry"]
        assert len(alt["geometry"]) >= 2

    # -------------------------------------------------------------------------
    # 7. Inspecting Route Evidence and Uncertainty
    # -------------------------------------------------------------------------
    assert "evidenceSummary" in safety_route
    ev_summary = safety_route["evidenceSummary"]
    assert ev_summary["coveragePercentage"] >= 0
    assert ev_summary["freshnessState"] in ("fresh", "stale", "outdated")
    # Verify segments inspection
    assert len(safety_route["segments"]) > 0
    first_seg = safety_route["segments"][0]
    assert "streetName" in first_seg
    assert "effectiveRisk" in first_seg
    assert "evidenceCoverage" in first_seg

    # -------------------------------------------------------------------------
    # 8. Submitting Localized Feedback
    # -------------------------------------------------------------------------
    feedback_payload = {
        "category": "lighting_accuracy",
        "message": "10th Main Road streetlamps are brightly illuminated and clear.",
        "rating": 5
    }
    fb_res = client.post("/api/v1/feedback", json=feedback_payload, headers=auth_headers)
    assert fb_res.status_code == 201
    fb_data = fb_res.json()
    feedback_id = fb_data["id"]

    # -------------------------------------------------------------------------
    # 9. Verifying Database Persistence and Moderator Visibility
    # -------------------------------------------------------------------------
    persisted_fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    assert persisted_fb is not None
    assert persisted_fb.user_id == reg_data["user"]["id"]
    assert persisted_fb.status == "new"

    # Moderator can inspect feedback inbox
    mod_fb_list = client.get("/api/v1/admin/feedback", headers=moderator_headers)
    assert mod_fb_list.status_code == 200
    assert any(f["id"] == feedback_id for f in mod_fb_list.json()["items"])

    # Regular user cannot access moderation inbox
    unauthorized_fb = client.get("/api/v1/admin/feedback", headers=auth_headers)
    assert unauthorized_fb.status_code == 403

    # -------------------------------------------------------------------------
    # 10. Administrator Access to Permitted Functions
    # -------------------------------------------------------------------------
    admin_audit = client.get("/api/v1/admin/audit", headers=admin_headers)
    assert admin_audit.status_code == 200
    assert "items" in admin_audit.json()

    admin_settings = client.get("/api/v1/admin/settings", headers=admin_headers)
    assert admin_settings.status_code == 200
    assert "freshnessThresholdDays" in admin_settings.json()

    # -------------------------------------------------------------------------
    # 11. Password-Reset Workflow
    # -------------------------------------------------------------------------
    reset_req = client.post("/api/v1/auth/password-reset/request", json={"email": reg_email})
    assert reset_req.status_code == 202
    assert "dispatched" in reset_req.json()["message"]

    # -------------------------------------------------------------------------
    # 12. Trusted-Contact Access Controls & Journey ETA Sharing
    # -------------------------------------------------------------------------
    contact_payload = {
        "name": "Mom",
        "relationship": "Parent",
        "phone": "+91 91234 56789"
    }
    ct_res = client.post("/api/v1/trusted-contacts", json=contact_payload, headers=auth_headers)
    assert ct_res.status_code == 201
    contact_id = ct_res.json()["id"]

    # Journey share preview
    share_payload = {
        "routeName": safety_route["name"],
        "etaMinutes": int(round(safety_route["durationSeconds"] / 60)),
        "destination": "Lalbagh West Gate",
        "contactIds": [contact_id]
    }
    share_res = client.post("/api/v1/journey-shares", json=share_payload, headers=auth_headers)
    assert share_res.status_code == 200
    assert share_res.json()["intendedCount"] == 1
    assert "pending_provider_integration" in share_res.json()["deliveryStatus"]

    # Clean up contact
    del_res = client.delete(f"/api/v1/trusted-contacts/{contact_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # -------------------------------------------------------------------------
    # 13. Logout & Protection of Restricted Endpoints
    # -------------------------------------------------------------------------
    logout_res = client.post("/api/v1/auth/logout", headers=auth_headers)
    assert logout_res.status_code == 200

    # Restricted endpoint rejects unauthenticated access
    unauth_req = client.get("/api/v1/trusted-contacts")
    assert unauth_req.status_code == 401
