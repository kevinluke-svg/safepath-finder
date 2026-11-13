import pytest
import uuid
import secrets
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

client = TestClient(app)

def test_complete_21_step_research_user_journey():
    """
    Validates the complete 21-step end-to-end user and research workflow
    for SafePath Finder Phase 4.
    """
    unique_suffix = secrets.token_hex(4)
    user_email = f"research_eval_{unique_suffix}@safepath.test"
    user_password = "SecureResearchPassword123!"
    user_name = f"Evaluator {unique_suffix}"

    # Step 1: Register
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": user_email,
        "password": user_password,
        "name": user_name
    })
    assert reg_resp.status_code in [200, 201], f"Register failed: {reg_resp.text}"
    user_data = reg_resp.json()
    user_id = user_data.get("id") or user_data.get("user", {}).get("id")
    assert user_id, "Missing user_id in registration response"

    # Step 2: Log in
    login_resp = client.post("/api/v1/auth/login", data={
        "username": user_email,
        "password": user_password
    })
    if login_resp.status_code == 422:
        login_resp = client.post("/api/v1/auth/login", json={
            "email": user_email,
            "password": user_password
        })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token_data = login_resp.json()
    access_token = token_data.get("accessToken") or token_data.get("access_token")
    assert access_token, "Missing access token"
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # Step 3: Search for a custom location
    search_resp = client.get("/api/v1/geocoding/search?q=Jayanagar+4th+Block")
    assert search_resp.status_code == 200, f"Search failed: {search_resp.text}"
    search_results = search_resp.json()["results"]
    assert len(search_results) > 0, "No search results returned"
    origin_name = search_results[0]["displayName"]
    origin_coords = [search_results[0]["latitude"], search_results[0]["longitude"]]

    # Step 4, 5, 6, 7: Generate fastest, balanced, safety-prioritized, and alternative routes
    route_payload = {
        "origin": "Jayanagar 4th Block, Bengaluru",
        "destination": "Lalbagh West Gate, Bengaluru",
        "originCoordinates": origin_coords,
        "destinationCoordinates": [12.9463, 77.5802],
        "walkingMode": "pedestrian",
        "departurePeriod": "evening",
        "preferences": {
            "includeAlternatives": True,
            "maxAlternatives": 3,
            "avoidPoorLighting": True
        }
    }
    compare_resp = client.post("/api/v1/routes/compare", json=route_payload)
    assert compare_resp.status_code == 200, f"Route compare failed: {compare_resp.text}"
    compare_data = compare_resp.json()
    routes = compare_data.get("routes", [])
    assert len(routes) >= 3, f"Expected at least 3 routes, got {len(routes)}"

    fastest_r = next((r for r in routes if r.get("category") == "fastest" or r.get("preference") == "Fastest"), None)
    balanced_r = next((r for r in routes if r.get("category") == "balanced" or r.get("preference") == "Balanced"), None)
    safety_r = next((r for r in routes if r.get("category") == "safety_prioritized" or r.get("preference") == "Safety-prioritized"), None)
    alt_routes = [r for r in routes if r.get("category") == "alternative"]

    assert fastest_r, "Fastest route missing"
    assert balanced_r, "Balanced route missing"
    assert safety_r, "Safety route missing"
    assert len(alt_routes) >= 1, "Alternative routes missing"

    # Step 8: Select and inspect a route
    selected_route = safety_r
    assert selected_route["distanceMeters"] > 0
    assert selected_route["durationSeconds"] > 0
    assert "walkingSpeedKmh" in selected_route

    # Step 9: Open Evidence Explorer (inspect overall route evidence)
    assert "evidenceCoverage" in selected_route
    assert "routeRisk" in selected_route

    # Step 10: Inspect streetlight evidence
    light_sum = selected_route.get("streetlightSummary", {})
    assert "litPercentage" in light_sum
    assert "unlitPercentage" in light_sum
    assert "unknownPercentage" in light_sum
    tot_light = light_sum["litPercentage"] + light_sum["unlitPercentage"] + light_sum["unknownPercentage"]
    assert abs(tot_light - 100.0) < 0.2

    # Step 11: Inspect crime evidence
    exp_details = selected_route.get("explanationDetails", {})
    assert "crimeNotice" in exp_details or "crimeEvidence" in exp_details

    # Step 12: Inspect dog encounters
    dog_sum = selected_route.get("dogEncounterSummary", {})
    assert "sightingCount" in dog_sum
    assert "aggressiveCount" in dog_sum
    assert "eligibleReportsCount" in dog_sum

    # Step 13: Inspect pedestrian infrastructure
    infra_sum = selected_route.get("pedestrianInfrastructureSummary", {})
    assert "knownSidewalkPercentage" in infra_sum or "sidewalkCoveragePercentage" in infra_sum
    assert "unmappedSidewalkPercentage" in infra_sum or "sidewalkUnmappedPercentage" in infra_sum

    # Step 14: View nearby facilities
    nearby = selected_route.get("nearbyPlaces", [])
    assert isinstance(nearby, list)
    for p in nearby[:3]:
        assert "distanceMeters" in p
        assert "distanceType" in p
        assert "source" in p
        assert "limitations" in p

    # Step 15: Submit a community report
    report_resp = client.post("/api/v1/reports", json={
        "category": "broken_lighting",
        "location": "10th Main Road, Jayanagar 4th Block",
        "description": "Streetlight fixture intermittently dark after 21:00.",
        "latitude": 12.9280,
        "longitude": 77.5835,
        "anonymous": True,
        "locationConfidence": "user_pinned"
    }, headers=auth_headers)
    assert report_resp.status_code in [200, 201], f"Report submit failed: {report_resp.text}"
    report_data = report_resp.json()
    report_id = report_data.get("id")
    assert report_id, "Missing report ID"
    assert report_data["status"] in ["pending", "flagged"]

    # Step 16: Moderate report as authorized administrator
    admin_token = create_access_token(subject="4cd2d987-2378-4197-b20e-321f894a6646", role="administrator")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    mod_resp = client.patch(f"/api/v1/admin/reports/{report_id}", json={
        "status": "approved",
        "reason": "Verified legitimate corridor lighting audit report."
    }, headers=admin_headers)
    assert mod_resp.status_code == 200, f"Moderation failed: {mod_resp.text}"
    assert mod_resp.json()["status"] == "approved"

    # Step 17: Manage trusted contacts
    contact_resp = client.post("/api/v1/trusted-contacts", json={
        "name": "Dr. Research Partner",
        "relationship": "Colleague",
        "phone": "+91 98765 43210",
        "notifyOnStart": True,
        "notifyOnArrival": True
    }, headers=auth_headers)
    assert contact_resp.status_code in [200, 201], f"Contact create failed: {contact_resp.text}"
    contact_data = contact_resp.json()
    contact_id = contact_data["id"]
    assert contact_data["phone"] == "+91 98765 43210"

    list_contacts = client.get("/api/v1/trusted-contacts", headers=auth_headers)
    assert list_contacts.status_code == 200
    assert any(c["id"] == contact_id for c in list_contacts.json())

    # Step 18: Share a journey
    session_start_resp = client.post("/api/v1/journey-sessions/start", json={
        "origin": "Jayanagar 4th Block",
        "destination": "Lalbagh West Gate",
        "routeName": "Safety-prioritized Route",
        "routeId": selected_route["id"],
        "etaMinutes": int(selected_route["durationSeconds"] / 60),
        "distanceMeters": int(selected_route["distanceMeters"]),
        "consentGiven": True,
        "contactIds": [contact_id]
    }, headers=auth_headers)
    assert session_start_resp.status_code in [200, 201], f"Journey start failed: {session_start_resp.text}"
    sess_data = session_start_resp.json()
    sess_id = sess_data["id"]
    sess_token = sess_data["token"]
    assert sess_data["status"] == "active"
    assert sess_data["isRevoked"] is False

    pub_view_resp = client.get(f"/api/v1/journey-shares/public/{sess_token}")
    assert pub_view_resp.status_code == 200
    pub_data = pub_view_resp.json()
    assert pub_data["destination"] == "Lalbagh West Gate"
    assert "email" not in pub_data and "phone" not in pub_data

    # Step 19: Revoke journey sharing
    cancel_resp = client.post(f"/api/v1/journey-sessions/{sess_id}/cancel", headers=auth_headers)
    assert cancel_resp.status_code == 200, f"Revocation failed: {cancel_resp.text}"
    cancelled_data = cancel_resp.json()
    assert cancelled_data["isRevoked"] is True
    assert cancelled_data["status"] == "cancelled"

    pub_view_revoked = client.get(f"/api/v1/journey-shares/public/{sess_token}")
    assert pub_view_revoked.status_code == 200
    assert pub_view_revoked.json()["status"] == "cancelled"

    # Step 20: Log out
    logout_resp = client.post("/api/v1/auth/logout", headers=auth_headers)
    assert logout_resp.status_code in [200, 204]

    # Step 21: Confirm protected endpoints reject unauthorized access
    unauth_resp = client.get("/api/v1/trusted-contacts")
    assert unauth_resp.status_code == 401, f"Expected 401 Unauthorized, got {unauth_resp.status_code}"

    unauth_post = client.post("/api/v1/trusted-contacts", json={
        "name": "Intruder",
        "phone": "+1 555 0199",
        "relationship": "None"
    })
    assert unauth_post.status_code == 401

    print("\nSUCCESS: Complete 21-step end-to-end research journey verified!")

def test_download_report_pdf_endpoint():
    """Validates the direct downloadable report PDF endpoint."""
    resp = client.get("/api/v1/download/report-pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert len(resp.content) > 100000
