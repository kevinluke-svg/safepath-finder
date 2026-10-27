from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_password, get_password_hash
from app.models.user import User


def test_registration_success(client: TestClient, db: Session):
    """Register a new traveller account."""
    payload = {
        "name": "Deepa Sundaram",
        "email": "deepa.sundaram@example.test",
        "password": "StrongPassword123!"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "accessToken" in data
    assert data["tokenType"] == "bearer"
    assert data["user"]["email"] == "deepa.sundaram@example.test"
    assert data["user"]["role"] == "traveller"

    # Verify database persistence & password hashing
    user = db.query(User).filter(User.email == "deepa.sundaram@example.test").first()
    assert user is not None
    assert user.hashed_password != payload["password"]
    assert verify_password(payload["password"], user.hashed_password)


def test_registration_duplicate_email(client: TestClient, traveller_user: User):
    """Duplicate email registration is rejected."""
    payload = {
        "name": "Duplicate User",
        "email": traveller_user.email,
        "password": "Password1234!"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_registration_short_password(client: TestClient):
    """Passwords shorter than 8 characters are rejected by validation."""
    payload = {
        "name": "Short Pass User",
        "email": "shortpass@example.test",
        "password": "short"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_password_hashing_argon2id():
    """Verify password hashing uses Argon2id."""
    password = "MySecurePassword123!"
    hashed = get_password_hash(password)
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_login_success(client: TestClient, traveller_user: User):
    """Authenticate with valid credentials and receive token."""
    payload = {
        "email": traveller_user.email,
        "password": "TravellerPass123!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert data["user"]["id"] == traveller_user.id


def test_login_wrong_password(client: TestClient, traveller_user: User):
    """Login with invalid password fails with 401."""
    payload = {
        "email": traveller_user.email,
        "password": "IncorrectPassword!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_login_nonexistent_user(client: TestClient):
    """Login with unknown email fails with 401."""
    payload = {
        "email": "nonexistent@safepath.test",
        "password": "SomePassword123!"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401


def test_password_reset_request_always_202(client: TestClient):
    """Password reset request always returns 202 without leaking account presence."""
    # Test for existing email
    res1 = client.post("/api/v1/auth/password-reset/request", json={"email": "priya.sharma@example.test"})
    assert res1.status_code == 202
    assert "password reset instructions" in res1.json()["message"]

    # Test for non-existent email
    res2 = client.post("/api/v1/auth/password-reset/request", json={"email": "unregistered@nowhere.test"})
    assert res2.status_code == 202
    assert res2.json()["message"] == res1.json()["message"]


def test_password_reset_confirm(client: TestClient, traveller_user: User):
    """Password reset confirm accepts single-use token and updates password."""
    from app.services import email_service

    # 1. Request reset
    req_res = client.post("/api/v1/auth/password-reset/request", json={"email": traveller_user.email})
    assert req_res.status_code == 202

    # 2. Extract dispatched token from test mailbox
    assert len(email_service.TEST_DISPATCHED_EMAILS) > 0
    raw_token = email_service.TEST_DISPATCHED_EMAILS[-1]["raw_token"]

    # 3. Confirm reset with token and new password
    new_pass = "NewStrongPassword123!"
    payload = {
        "token": raw_token,
        "password": new_pass
    }
    response = client.post("/api/v1/auth/password-reset/confirm", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 4. Invalidate token on use (reused token rejected with 400)
    reused_res = client.post("/api/v1/auth/password-reset/confirm", json=payload)
    assert reused_res.status_code == 400

    # 5. User can log in with new password
    login_res = client.post("/api/v1/auth/login", json={"email": traveller_user.email, "password": new_pass})
    assert login_res.status_code == 200
    assert "accessToken" in login_res.json()



def test_get_current_user_me(client: TestClient, traveller_headers: dict, traveller_user: User):
    """GET /api/v1/me returns authenticated user's profile."""
    response = client.get("/api/v1/me", headers=traveller_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == traveller_user.id
    assert data["email"] == traveller_user.email
    assert data["role"] == "traveller"


def test_unauthenticated_protected_endpoint(client: TestClient):
    """Protected endpoints reject requests without Authorization header."""
    response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_logout(client: TestClient, traveller_headers: dict):
    """Logout terminates session and returns success."""
    response = client.post("/api/v1/auth/logout", headers=traveller_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True
