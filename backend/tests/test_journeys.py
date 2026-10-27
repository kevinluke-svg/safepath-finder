from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User


def test_save_and_list_journeys(client: TestClient, traveller_headers: dict):
    """Save a journey plan and verify listing."""
    payload = {
        "start": "Jayanagar 4th Block",
        "end": "Lalbagh West Gate",
        "routeId": "route-evidence",
        "routeName": "Evidence-led Route",
        "distanceMeters": 1850,
        "durationMinutes": 24,
        "preferences": {"preferLighting": True}
    }
    create_res = client.post("/api/v1/journeys", json=payload, headers=traveller_headers)
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    list_res = client.get("/api/v1/journeys", headers=traveller_headers)
    assert list_res.status_code == 200
    journeys = list_res.json()
    assert any(j["id"] == created_id for j in journeys)


def test_cross_user_journey_deletion_prevented(
    client: TestClient,
    traveller_headers: dict,
    other_traveller_headers: dict
):
    """User B cannot delete User A's saved journey (IDOR Prevention)."""
    # Traveller A creates a plan
    payload = {
        "start": "User A Home",
        "end": "User A Work",
        "routeId": "route-evidence",
        "routeName": "A Route",
        "distanceMeters": 1200,
        "durationMinutes": 15
    }
    create_res = client.post("/api/v1/journeys", json=payload, headers=traveller_headers)
    plan_id = create_res.json()["id"]

    # Traveller B tries to delete Traveller A's plan
    del_res = client.delete(f"/api/v1/journeys/{plan_id}", headers=other_traveller_headers)
    assert del_res.status_code == 403
    assert "not authorized" in del_res.json()["detail"]

    # Traveller A can successfully delete their own plan
    owner_del = client.delete(f"/api/v1/journeys/{plan_id}", headers=traveller_headers)
    assert owner_del.status_code == 200
    assert owner_del.json()["success"] is True


def test_saved_places_crud_and_isolation(
    client: TestClient,
    traveller_headers: dict,
    other_traveller_headers: dict
):
    """Saved places CRUD with strict cross-user isolation."""
    # Create place
    payload = {"label": "Home", "address": "11th Main Jayanagar", "icon": "home"}
    create_res = client.post("/api/v1/saved-places", json=payload, headers=traveller_headers)
    assert create_res.status_code == 201
    place_id = create_res.json()["id"]

    # List places for creator
    list_res = client.get("/api/v1/saved-places", headers=traveller_headers)
    assert any(p["id"] == place_id for p in list_res.json())

    # Other user does not see creator's place
    other_list = client.get("/api/v1/saved-places", headers=other_traveller_headers)
    assert not any(p["id"] == place_id for p in other_list.json())

    # Other user cannot delete creator's place
    del_attempt = client.delete(f"/api/v1/saved-places/{place_id}", headers=other_traveller_headers)
    assert del_attempt.status_code == 403

    # Creator can delete their own place
    owner_del = client.delete(f"/api/v1/saved-places/{place_id}", headers=traveller_headers)
    assert owner_del.status_code == 200
