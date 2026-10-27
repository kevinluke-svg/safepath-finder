import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.user import User
from app.models.contact import TrustedContact
from app.models.audit import AuditLog


def test_admin_user_list_masking_by_default(client: TestClient, admin_headers: dict, traveller_user: User):
    """
    Priority 2: The administrator user management list must NOT display plaintext personal names
    or unmasked emails. It must provide pseudonymous identifiers and masked emails.
    """
    response = client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0

    target = next((u for u in data["items"] if u["id"] == traveller_user.id), None)
    assert target is not None, "Traveller user not found in admin list"

    # Invariants: No plaintext name or plaintext email in response
    assert "name" not in target, "Plaintext name must not be present in AdminUserResponse"
    assert "email" not in target, "Plaintext email must not be present in AdminUserResponse"

    # Invariants: Masked email and pseudonymous display name are provided
    assert "emailMasked" in target
    assert "@" in target["emailMasked"]
    assert "***" in target["emailMasked"]
    assert target["displayName"] == f"User-{traveller_user.id[:8]}"


def test_unauthorized_user_cannot_reveal_identity(client: TestClient, moderator_headers: dict, traveller_headers: dict, traveller_user: User):
    """Non-administrators (moderators and travellers) are forbidden from revealing identity."""
    payload = {"reason": "Attempting unauthorized identity inspection"}
    
    # Moderator attempt
    res_mod = client.post(f"/api/v1/admin/users/{traveller_user.id}/reveal-identity", json=payload, headers=moderator_headers)
    assert res_mod.status_code == 403

    # Traveller attempt
    res_trav = client.post(f"/api/v1/admin/users/{traveller_user.id}/reveal-identity", json=payload, headers=traveller_headers)
    assert res_trav.status_code == 403


def test_admin_reveal_identity_audited(client: TestClient, admin_headers: dict, traveller_user: User, db: Session):
    """
    Authorized administrator can reveal identity only by providing a justification,
    and this action must be recorded in the audit trail.
    """
    # 1. Require reason (min 5 chars)
    bad_res = client.post(f"/api/v1/admin/users/{traveller_user.id}/reveal-identity", json={"reason": "bad"}, headers=admin_headers)
    assert bad_res.status_code == 422

    # 2. Valid revelation
    reason = "Customer support ticket #12344 - account recovery verification"
    res = client.post(f"/api/v1/admin/users/{traveller_user.id}/reveal-identity", json={"reason": reason}, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == traveller_user.name
    assert data["email"] == traveller_user.email
    assert data["justification"] == reason
    assert "revealedAt" in data

    # 3. Verify audit log entry was written
    audit = db.query(AuditLog).filter(
        AuditLog.action == "Sensitive Identity Revealed"
    ).order_by(AuditLog.timestamp.desc()).first()
    assert audit is not None
    assert traveller_user.id in audit.record
    assert reason in audit.record


def test_contact_encryption_at_rest(client: TestClient, traveller_headers: dict, db: Session):
    """
    Priority 6: Trusted contact names and phone numbers must be encrypted with AES-128 Fernet at rest.
    Direct SQL inspection must reveal ciphertext, while authorized GET returns decrypted plaintext.
    """
    raw_name = "Kavitha Raman"
    raw_phone = "+91 99887 76655"
    payload = {
        "name": raw_name,
        "relationship": "Colleague",
        "phone": raw_phone
    }
    create_res = client.post("/api/v1/trusted-contacts", json=payload, headers=traveller_headers)
    assert create_res.status_code == 201
    contact_id = create_res.json()["id"]

    # 1. Query raw database row directly using raw SQL
    row = db.execute(text("SELECT name, phone FROM trusted_contacts WHERE id = :id"), {"id": contact_id}).fetchone()
    assert row is not None
    db_raw_name, db_raw_phone = row[0], row[1]

    # Must NOT be stored in plaintext
    assert db_raw_name != raw_name, "Contact name was stored in plaintext!"
    assert db_raw_phone != raw_phone, "Contact phone was stored in plaintext!"

    # Must be Fernet ciphertext format (starts with gAAAAA)
    assert db_raw_name.startswith("gAAAAA"), f"Unexpected ciphertext format: {db_raw_name}"
    assert db_raw_phone.startswith("gAAAAA"), f"Unexpected ciphertext format: {db_raw_phone}"

    # 2. Owner API GET must return decrypted plaintext
    list_res = client.get("/api/v1/trusted-contacts", headers=traveller_headers)
    assert list_res.status_code == 200
    my_contact = next((c for c in list_res.json() if c["id"] == contact_id), None)
    assert my_contact is not None
    assert my_contact["name"] == raw_name
    assert my_contact["phone"] == raw_phone


def test_contact_update_owner_only(client: TestClient, traveller_headers: dict, other_traveller_headers: dict):
    """Owner can update contact; non-owner is forbidden (403)."""
    # Create contact
    payload = {
        "name": "Initial Name",
        "relationship": "Friend",
        "phone": "+91 91234 56789"
    }
    res = client.post("/api/v1/trusted-contacts", json=payload, headers=traveller_headers)
    contact_id = res.json()["id"]

    # Other user attempt update -> 403
    update_attempt = client.patch(
        f"/api/v1/trusted-contacts/{contact_id}",
        json={"name": "Hacked Name"},
        headers=other_traveller_headers
    )
    assert update_attempt.status_code == 403

    # Owner update -> 200
    owner_update = client.patch(
        f"/api/v1/trusted-contacts/{contact_id}",
        json={"name": "Updated Name", "relationship": "Sister"},
        headers=traveller_headers
    )
    assert owner_update.status_code == 200
    assert owner_update.json()["name"] == "Updated Name"
    assert owner_update.json()["relationship"] == "Sister"
