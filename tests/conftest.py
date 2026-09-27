"""
Pytest configuration and fixtures
"""
import pytest
import os

# IMPORTANT: Set test database URL BEFORE importing models
# This ensures models use JSON instead of JSONB for SQLite compatibility
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.database import Base, get_db
from src.main import app

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database dependency override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def fixture_path():
    """Return path to fixtures directory"""
    # Tests are in /app/tests, fixtures are in /Users/.../Backend_Engineer.../fixtures
    # In Docker, we need to use the mounted path
    # Check if running in Docker or locally
    docker_fixture_path = "/fixtures"
    local_fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "fixtures"
    )

    # Try Docker path first
    if os.path.exists(docker_fixture_path):
        return docker_fixture_path
    # Fall back to local path
    elif os.path.exists(local_fixture_path):
        return local_fixture_path
    else:
        # Last resort: relative path
        return "../fixtures"
