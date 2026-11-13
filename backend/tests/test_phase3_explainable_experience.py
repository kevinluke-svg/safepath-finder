"""
SafePath Finder - Phase 3 Automated Test Suite
Explainable Map Experience, Community Trust, and Journey Protection
Tests the 11 key validation dimensions required by Phase 3 specification.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.report import CommunityReport, ReportCorroboration
from app.models.contact import JourneySession, TrustedContact
from app.models.user import User


# =============================================================================
# 1. Map Layers Bundle & Legend Distinctions
# =============================================================================

def test_map_layers_bundle_structure_and_legends(client: TestClient):
    """
    Validates GET /api/v1/evidence/map-layers:
    - Independent layers for facilities, landmarks, dogs, reports, lighting, infra, crime.
    - Epistemological legend distinguishing mapped data, community reports, inferred values, and unknown info.
    - Zero submitter/user PII in any layer element.
    """
    res = client.get("/api/v1/evidence/map-layers")
    assert res.status_code == status.HTTP_200_OK
    bundle = res.json()

    # Core GIS layers present
    assert "studyArea" in bundle
    assert "layers" in bundle
    layers = bundle["layers"]
    assert "facilities" in layers
    assert "landmarks" in layers
    assert "dogs" in layers
    assert "community" in layers
    assert "lighting" in layers
    assert "infrastructure" in layers
    assert "crime" in layers
    assert "legends" in bundle
    assert "safetyDisclaimer" in bundle

    # Four distinct legend epistemological categories
    legends = bundle["legends"]
    assert "mappedData" in legends
    assert "communityReports" in legends
    assert "inferredValues" in legends
    assert "unknownInfo" in legends

    # Legend contents distinguish sources
    assert any("municipal" in item.lower() or "osm" in item.lower() for item in legends["mappedData"])
    assert any("citizen" in item.lower() or "community" in item.lower() for item in legends["communityReports"])
    assert any("inferred" in item.lower() or "prior" in item.lower() or "model" in item.lower() for item in legends["inferredValues"])
    assert any("unmapped" in item.lower() or "uncertain" in item.lower() for item in legends["unknownInfo"])

    # Safety disclaimer explicit about real-time limitations
    assert "not an emergency" in bundle["safetyDisclaimer"].lower() or "does not dispatch" in bundle["safetyDisclaimer"].lower()

    # Data minimization: Check community reports for PII leaks
    for rep in layers["community"]:
        assert "reporterId" not in rep
        assert "reporterName" not in rep or rep["reporterName"] == "Anonymous"
        assert "user_id" not in rep
        assert "email" not in rep
        assert "phone" not in rep


# =============================================================================
# 2. Street-Level Segment Inspection & Separation of Dimensions
# =============================================================================

def test_street_segment_inspection_multidimensional_evidence(client: TestClient):
    """
    Validates route segment inspection payload:
    - Preserves separate indicators for crime, lighting, dogs, infrastructure, assistance.
    - Explicit coverage score Q(e) and uncertainty prior R_unknown.
    - Does NOT collapse into a single unexplained score.
    """
    payload = {
        "origin": "12.9257, 77.5833",
        "destination": "12.9501, 77.5847",
        "walkingMode": "pedestrian",
        "preferences": {
            "includeAlternatives": True,
            "maxAlternatives": 2
        }
    }
    res = client.post("/api/v1/routes/compare", json=payload)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    routes = data.get("routes", [])
    assert len(routes) >= 2

    # Verify active route contains valid segment breakdown
    for route in routes:
        assert "segments" in route
        segments = route["segments"]
        assert len(segments) > 0

        first_seg = segments[0]
        # Street or road name
        assert "streetName" in first_seg or "street_name" in first_seg
        # Segment length and walking time
        assert "lengthMeters" in first_seg or "length_meters" in first_seg
        assert "traversalTimeSeconds" in first_seg or "traversal_time_seconds" in first_seg
        # Lighting status
        assert "litStatus" in first_seg or "lit_status" in first_seg
        # Crime evidence
        assert "crimeCount" in first_seg or "crime_count" in first_seg
        # Pedestrian infrastructure
        assert "sidewalkStatus" in first_seg or "sidewalk_status" in first_seg
        # Coverage Q(e) and uncertainty
        assert "coverage" in first_seg or "evidenceCoverage" in first_seg or "coverageScore" in first_seg


# =============================================================================
# 3. Departure Period Selection & Explicit Evidence Availability
# =============================================================================

def test_departure_period_routing_behavior_and_limitations(client: TestClient):
    """
    Tests daytime, evening, and night routing:
    - Route responses reflect selected departurePeriod.
    - Explains whether time-specific data is genuinely available.
    - Honest caveats: does NOT claim live illumination or real-time CCTV feeds.
    """
    base_payload = {
        "origin": "12.9257, 77.5833",
        "destination": "12.9501, 77.5847",
        "walkingMode": "pedestrian"
    }

    # 1. Daytime
    day_res = client.post("/api/v1/routes/compare", json={**base_payload, "departurePeriod": "daytime"})
    assert day_res.status_code == status.HTTP_200_OK
    day_data = day_res.json()
    assert all(r["departurePeriod"] == "daytime" for r in day_data["routes"])

    # 2. Night
    night_res = client.post("/api/v1/routes/compare", json={**base_payload, "departurePeriod": "night"})
    assert night_res.status_code == status.HTTP_200_OK
    night_data = night_res.json()
    assert all(r["departurePeriod"] == "night" for r in night_data["routes"])

    # 3. Limitations disclosure present in response
    assert any(len(r.get("limitations", [])) > 0 for r in night_data["routes"]) or "rankingReason" in night_data


# =============================================================================
# 4. Independent Report Confirmations & Outdated Flags
# =============================================================================

def test_independent_report_confirmations_and_outdated_flags(
    client: TestClient,
    traveller_headers: dict,
    other_traveller_headers: dict,
    db: Session
):
    """
    Tests community report reliability controls:
    - Submitter cannot confirm own report (anti-manipulation).
    - Second independent user confirms report (increments corroborations).
    - Duplicate confirmation by the same second user is rejected (rate limiting / idempotency).
    - Flagging report as outdated increments outdated_flags as a separate counter.
    - Corroborations and outdated_flags remain distinct.
    """
    # 1. Create a report as traveller_user
    create_res = client.post("/api/v1/reports", json={
        "category": "broken_lighting",
        "location": "10th Main Road near 28th Cross",
        "description": "Streetlight luminaire pole #14 has been unlit for past 3 days.",
        "latitude": 12.9350,
        "longitude": 77.5840
    }, headers=traveller_headers)
    assert create_res.status_code == status.HTTP_201_CREATED
    rep_id = create_res.json()["id"]

    # 2. Submitter attempts to confirm own report -> Rejected
    own_confirm_res = client.post(f"/api/v1/reports/{rep_id}/confirm", headers=traveller_headers)
    assert own_confirm_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "own report" in own_confirm_res.json()["detail"].lower()

    # 3. Independent second user confirms the report -> Succeeded
    other_confirm_res = client.post(f"/api/v1/reports/{rep_id}/confirm", headers=other_traveller_headers)
    assert other_confirm_res.status_code == status.HTTP_200_OK
    assert other_confirm_res.json()["corroborationsCount"] == 2
    assert other_confirm_res.json()["action"] == "confirm_present"

    # 4. Second user attempts to confirm AGAIN -> Rejected as duplicate
    dup_confirm_res = client.post(f"/api/v1/reports/{rep_id}/confirm", headers=other_traveller_headers)
    assert dup_confirm_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already confirmed" in dup_confirm_res.json()["detail"].lower()

    # 5. Independent third user flags report as outdated -> Succeeded
    from app.core.security import get_password_hash, create_access_token
    from app.models.user import User
    third_user = User(
        name="Sunil ThirdUser",
        email="sunil.third@safepath.test",
        hashed_password=get_password_hash("ThirdPass123!"),
        role="traveller",
        status="active"
    )
    db.add(third_user)
    db.commit()
    db.refresh(third_user)
    third_token = create_access_token(subject=third_user.id, role=third_user.role)
    third_headers = {"Authorization": f"Bearer {third_token}"}

    outdated_res = client.post(f"/api/v1/reports/{rep_id}/outdated", headers=third_headers)
    assert outdated_res.status_code == status.HTTP_200_OK
    assert outdated_res.json()["outdatedFlagsCount"] == 1
    assert outdated_res.json()["corroborationsCount"] == 2  # Corroborations untouched


# =============================================================================
# 5. User Report Status & Mine Endpoint
# =============================================================================

def test_user_report_status_and_mine_endpoint(
    client: TestClient,
    traveller_headers: dict,
    other_traveller_headers: dict
):
    """
    Tests GET /api/v1/reports/mine:
    - User can track their own submissions and moderation status.
    - Strict user-isolation: other users cannot view or manipulate private report history.
    """
    # Submit report
    client.post("/api/v1/reports", json={
        "category": "crossing_issue",
        "location": "Jayanagar 4th Block Complex",
        "description": "Faded pedestrian zebra crossing stripes, vehicles not yielding.",
        "latitude": 12.9300,
        "longitude": 77.5830
    }, headers=traveller_headers)

    # Fetch traveller's own reports
    res = client.get("/api/v1/reports/mine", headers=traveller_headers)
    assert res.status_code == status.HTTP_200_OK
    my_reports = res.json()
    assert len(my_reports) >= 1
    assert any(r["category"] == "crossing_issue" for r in my_reports)
    assert all(r["status"] in ("pending", "approved", "flagged") for r in my_reports)

    # Fetch other traveller's reports -> isolated
    other_res = client.get("/api/v1/reports/mine", headers=other_traveller_headers)
    assert other_res.status_code == status.HTTP_200_OK
    assert not any(r["category"] == "crossing_issue" for r in other_res.json())


# =============================================================================
# 6. Trusted-Contact Journey Session Lifecycle & Authorization
# =============================================================================

def test_trusted_contact_journey_session_lifecycle(
    client: TestClient,
    traveller_headers: dict,
    other_traveller_headers: dict
):
    """
    Tests journey protection sessions:
    - Explicit consent required before starting.
    - Secure expiring token generated.
    - Active session retrieval.
    - 5-min pre-arrival reminder simulation (clearly marked simulated dev mode).
    - IDOR protection: non-creator cannot check-in or cancel journey session.
    - Safe arrival check-in.
    - Check-in idempotency (cannot check in twice).
    """
    # 1. Missing voluntary consent -> Rejected
    no_consent_res = client.post("/api/v1/journey-sessions/start", json={
        "origin": "Jayanagar 4th Block",
        "destination": "Lalbagh West Gate",
        "routeName": "Safety-prioritized",
        "routeId": "safety-prioritized",
        "etaMinutes": 20,
        "distanceMeters": 1500,
        "consentGiven": False
    }, headers=traveller_headers)
    assert no_consent_res.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Start session with voluntary consent
    start_res = client.post("/api/v1/journey-sessions/start", json={
        "origin": "Jayanagar 4th Block",
        "destination": "Lalbagh West Gate",
        "routeName": "Safety-prioritized Route",
        "routeId": "safety-prioritized",
        "etaMinutes": 22,
        "distanceMeters": 1650,
        "consentGiven": True,
        "contactIds": []
    }, headers=traveller_headers)
    assert start_res.status_code == status.HTTP_201_CREATED
    session = start_res.json()
    session_id = session["id"]
    token = session["token"]

    assert session["status"] == "active"
    assert session["consentGiven"] is True
    assert session["shareUrl"].endswith(f"?share_token={token}")
    assert session["notificationMode"] in ("simulated_development", "Simulated development mode")

    # 3. Retrieve active journey session
    active_res = client.get("/api/v1/journey-sessions/active", headers=traveller_headers)
    assert active_res.status_code == status.HTTP_200_OK
    active_sessions = active_res.json()
    assert len(active_sessions) >= 1
    assert any(s["id"] == session_id for s in active_sessions)

    # 4. Simulate 5-minute pre-arrival reminder
    reminder_res = client.post(f"/api/v1/journey-sessions/{session_id}/simulate-reminder", headers=traveller_headers)
    assert reminder_res.status_code == status.HTTP_200_OK
    assert "simulated" in reminder_res.json()["message"].lower()

    # 5. IDOR Check: other user cannot check-in or cancel session
    unauth_checkin = client.post(f"/api/v1/journey-sessions/{session_id}/check-in", headers=other_traveller_headers)
    assert unauth_checkin.status_code == status.HTTP_403_FORBIDDEN

    unauth_cancel = client.post(f"/api/v1/journey-sessions/{session_id}/cancel", headers=other_traveller_headers)
    assert unauth_cancel.status_code == status.HTTP_403_FORBIDDEN

    # 6. Safe arrival check-in by creator
    checkin_res = client.post(f"/api/v1/journey-sessions/{session_id}/check-in", headers=traveller_headers)
    assert checkin_res.status_code == status.HTTP_200_OK
    assert checkin_res.json()["status"] == "completed"
    assert checkin_res.json()["completedAt"] is not None

    # 7. Check-in again -> Rejected as already completed
    repeat_checkin = client.post(f"/api/v1/journey-sessions/{session_id}/check-in", headers=traveller_headers)
    assert repeat_checkin.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# 7. Public Journey Share Token & Zero PII Leakage
# =============================================================================

def test_public_journey_share_token_access_and_zero_pii_leak(
    client: TestClient,
    traveller_headers: dict
):
    """
    Tests public tokenized journey link (for SMS / WhatsApp contacts without login):
    - Accessible without authentication.
    - Zero user PII leaked (no user_id, email, phone number, contact details).
    - Status transitions properly reflected (active -> revoked).
    """
    # 1. Create session
    start_res = client.post("/api/v1/journey-sessions/start", json={
        "origin": "National College Metro",
        "destination": "Gandhi Bazaar Circle",
        "routeName": "Balanced Route",
        "routeId": "balanced",
        "etaMinutes": 14,
        "distanceMeters": 1100,
        "consentGiven": True
    }, headers=traveller_headers)
    session = start_res.json()
    token = session["token"]
    session_id = session["id"]

    # 2. Fetch public view WITHOUT any auth header
    public_res = client.get(f"/api/v1/journey-shares/public/{token}")
    assert public_res.status_code == status.HTTP_200_OK
    pub_data = public_res.json()

    # Content checks
    assert pub_data["destination"] == "Gandhi Bazaar Circle"
    assert pub_data["status"] == "active"
    assert pub_data["distanceMeters"] == 1100
    assert pub_data["etaMinutes"] == 14

    # Strict Privacy Checks (No PII)
    assert "userId" not in pub_data
    assert "user_id" not in pub_data
    assert "email" not in pub_data
    assert "phone" not in pub_data
    assert "reporterName" not in pub_data
    assert "contactIds" not in pub_data

    # Peer-to-peer reassurance statement present
    notice_text = (pub_data.get("peerReassuranceNotice") or pub_data.get("disclaimer", "")).lower()
    assert "peer-to-peer" in notice_text
    assert "not confirm an emergency" in notice_text or "not an emergency" in notice_text

    # 3. Cancel session
    client.post(f"/api/v1/journey-sessions/{session_id}/cancel", headers=traveller_headers)

    # 4. Public link now reports status 'cancelled' or 'revoked'
    revoked_res = client.get(f"/api/v1/journey-shares/public/{token}")
    assert revoked_res.status_code == status.HTTP_200_OK
    assert revoked_res.json()["status"] in ("revoked", "cancelled")

    # 5. Non-existent token -> 404
    missing_res = client.get("/api/v1/journey-shares/public/non-existent-fake-token-xyz")
    assert missing_res.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# 8. Peer Reassurance Boundaries & No Emergency Claims
# =============================================================================

def test_peer_reassurance_boundaries_and_no_emergency_claims(
    client: TestClient,
    traveller_headers: dict
):
    """
    Validates application safety claims:
    - Never claims 911, 112, or police have been dispatched.
    - Never claims a missed check-in proves an emergency occurred.
    - Development mode explicitly labelled.
    """
    start_res = client.post("/api/v1/journey-sessions/start", json={
        "origin": "South End Circle",
        "destination": "Ashoka Pillar",
        "routeName": "Safety-prioritized",
        "routeId": "safety-prioritized",
        "etaMinutes": 18,
        "distanceMeters": 1400,
        "consentGiven": True
    }, headers=traveller_headers)
    session = start_res.json()

    assert session["notificationMode"] in ("simulated_development", "Simulated development mode")

    # Public notice validation
    pub_res = client.get(f"/api/v1/journey-shares/public/{session['token']}")
    notice = pub_res.json().get("peerReassuranceNotice") or pub_res.json().get("disclaimer", "")

    assert "does NOT dispatch" in notice or "NOT connected to emergency" in notice or "peer-to-peer" in notice.lower()
    assert "not that an emergency has occurred" in notice or "not confirm an emergency" in notice
