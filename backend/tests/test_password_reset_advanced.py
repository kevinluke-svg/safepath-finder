from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import hashlib

from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.services import email_service


def test_password_reset_token_hashed_at_rest(client: TestClient, traveller_user: User, db: Session):
    """
    Priority 3: Password reset tokens must NEVER be stored in plaintext.
    Only their cryptographic hash (SHA-256) is stored in the database.
    """
    email_service.TEST_DISPATCHED_EMAILS.clear()
    res = client.post("/api/v1/auth/password-reset/request", json={"email": traveller_user.email})
    assert res.status_code == 202

    assert len(email_service.TEST_DISPATCHED_EMAILS) > 0
    raw_token = email_service.TEST_DISPATCHED_EMAILS[-1]["raw_token"]
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Query DB row
    token_record = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == traveller_user.id).order_by(PasswordResetToken.created_at.desc()).first()
    assert token_record is not None
    assert token_record.token_hash == expected_hash
    assert token_record.token_hash != raw_token, "Plaintext token found in database!"


def test_expired_reset_token_rejected(client: TestClient, traveller_user: User, db: Session):
    """Expired reset tokens must be rejected with 400."""
    email_service.TEST_DISPATCHED_EMAILS.clear()
    client.post("/api/v1/auth/password-reset/request", json={"email": traveller_user.email})
    raw_token = email_service.TEST_DISPATCHED_EMAILS[-1]["raw_token"]

    # Manually expire the token in the database
    token_record = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == traveller_user.id).order_by(PasswordResetToken.created_at.desc()).first()
    assert token_record is not None
    token_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    # Attempt confirm
    confirm_res = client.post("/api/v1/auth/password-reset/confirm", json={
        "token": raw_token,
        "password": "ValidPassword987!"
    })
    assert confirm_res.status_code == 400
    assert "expired" in confirm_res.json()["detail"].lower()


def test_password_reset_rate_limiting(client: TestClient, traveller_user: User, db: Session):
    """Reset requests are rate-limited to 3 per 15-minute window for a user."""
    email_service.TEST_DISPATCHED_EMAILS.clear()

    # 3 allowed requests
    for i in range(3):
        res = client.post("/api/v1/auth/password-reset/request", json={"email": traveller_user.email})
        assert res.status_code == 202

    tokens_count_before = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == traveller_user.id).count()

    # 4th request: response is still neutral 202 (no leak), but NO new token record is created!
    res_4 = client.post("/api/v1/auth/password-reset/request", json={"email": traveller_user.email})
    assert res_4.status_code == 202

    tokens_count_after = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == traveller_user.id).count()
    assert tokens_count_after == tokens_count_before, "Rate limit failed: token created despite limit exceeded!"
