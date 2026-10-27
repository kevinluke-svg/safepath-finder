import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import get_db
from app.models.base import Base
from app.models.user import User
from app.core.security import get_password_hash, create_access_token
from app.db.seed import seed_database

# Use in-memory SQLite for fast, isolated test execution
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in memory once for the session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Provide a fresh transactional session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    # Seed default fixtures
    seed_database(session)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def traveller_user(db: Session) -> User:
    """Create a standard traveller user."""
    user = User(
        name="Priya Sharma",
        email="priya.sharma@example.test",
        hashed_password=get_password_hash("TravellerPass123!"),
        role="traveller",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def traveller_token(traveller_user: User) -> str:
    return create_access_token(subject=traveller_user.id, role=traveller_user.role)


@pytest.fixture
def traveller_headers(traveller_token: str) -> dict:
    return {"Authorization": f"Bearer {traveller_token}"}


@pytest.fixture
def other_traveller_user(db: Session) -> User:
    """Create a second traveller to test cross-user authorization boundaries (IDOR)."""
    user = User(
        name="Ananya Rao",
        email="ananya.rao@example.test",
        hashed_password=get_password_hash("OtherPass123!"),
        role="traveller",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_traveller_headers(other_traveller_user: User) -> dict:
    token = create_access_token(subject=other_traveller_user.id, role=other_traveller_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def moderator_user(db: Session) -> User:
    """Create a moderator user."""
    user = User(
        name="Arun Moderator",
        email="arun.mod@safepath.test",
        hashed_password=get_password_hash("ModeratorPass123!"),
        role="moderator",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def moderator_headers(moderator_user: User) -> dict:
    token = create_access_token(subject=moderator_user.id, role=moderator_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(db: Session) -> User:
    """Create an administrator user."""
    user = User(
        name="Kavitha Administrator",
        email="kavitha.admin@safepath.test",
        hashed_password=get_password_hash("AdminPass123!"),
        role="administrator",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user: User) -> dict:
    token = create_access_token(subject=admin_user.id, role=admin_user.role)
    return {"Authorization": f"Bearer {token}"}
