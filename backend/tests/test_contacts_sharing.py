from fastapi.testclient import TestClient


def test_trusted_contacts_crud_and_isolation(
    client: TestClient,
    traveller_headers: dict,
    other_traveller_headers: dict
):
    """Add, list, and delete trusted contacts with cross-user isolation."""
    # Add contact
    payload = {
        "name": "Sister Maya",
        "relationship": "Sister",
        "phone": "+91 98765 43210"
    }
    create_res = client.post("/api/v1/trusted-contacts", json=payload, headers=traveller_headers)
    assert create_res.status_code == 201
    contact_id = create_res.json()["id"]

    # Verify listing for owner
    list_res = client.get("/api/v1/trusted-contacts", headers=traveller_headers)
    assert any(c["id"] == contact_id for c in list_res.json())

    # Verify other user cannot see owner's contact
    other_list = client.get("/api/v1/trusted-contacts", headers=other_traveller_headers)
    assert not any(c["id"] == contact_id for c in other_list.json())

    # Cross-user deletion attempt blocked
    del_attempt = client.delete(f"/api/v1/trusted-contacts/{contact_id}", headers=other_traveller_headers)
    assert del_attempt.status_code == 403

    # Owner can delete
    owner_del = client.delete(f"/api/v1/trusted-contacts/{contact_id}", headers=traveller_headers)
    assert owner_del.status_code == 200


def test_journey_share_delivery_honesty(client: TestClient, traveller_headers: dict):
    """
    POST /api/v1/journey-shares must NOT claim successful delivery without provider integration.
    Verifies deliveryStatus is pending_provider_integration.
    """
    payload = {
        "routeName": "Evidence-led Route",
        "etaMinutes": 24,
        "destination": "Lalbagh West Gate",
        "contactIds": ["ct-demo-1", "ct-demo-2"]
    }
    response = client.post("/api/v1/journey-shares", json=payload, headers=traveller_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["deliveryStatus"] == "pending_provider_integration"
    assert "Backend integration required" in data["providerName"]
    assert data["intendedCount"] == 2
    assert data["deliveredCount"] == 0
    assert "preview_journey=true" in data["shareLink"]


def test_arrival_confirmation_delivery_honesty(client: TestClient, traveller_headers: dict):
    """
    POST /api/v1/arrival-confirmations records arrival and informs user of gateway integration boundary.
    """
    payload = {
        "destination": "Lalbagh West Gate",
        "journeyId": "jrn-active-demo"
    }
    response = client.post("/api/v1/arrival-confirmations", json=payload, headers=traveller_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["arrivalConfirmed"] is True
    assert data["deliveryStatus"] == "pending_provider_integration"
    assert "SMS gateway integration" in data["message"]
