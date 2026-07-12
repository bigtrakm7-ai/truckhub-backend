"""Integration tests for TruckGrad API.

Tests full request/response cycles with database.
"""

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings

# Test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create test database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ── Auth Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpassword123",
        "role": "buyer",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_login_user(client: AsyncClient):
    """Test user login."""
    # First register
    await client.post("/api/v1/auth/register", json={
        "email": "login@test.com",
        "password": "testpass123",
        "role": "buyer",
    })
    
    # Then login
    response = await client.post("/api/v1/auth/login", data={
        "username": "login@test.com",
        "password": "testpass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


# ── Catalog Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_products(client: AsyncClient):
    """Test product search."""
    response = await client.get("/api/v1/catalog/search?q=фильтр")
    assert response.status_code == 200
    data = response.json()
    assert "products" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_categories(client: AsyncClient):
    """Test getting categories."""
    response = await client.get("/api/v1/catalog/categories")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data


# ── VIN Decoder Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vin_decode(client: AsyncClient):
    """Test VIN decoding."""
    response = await client.get("/api/v1/catalog/vin/XTA6425KLA0000001")
    assert response.status_code == 200
    data = response.json()
    assert data["vin"] == "XTA6425KLA0000001"
    assert data["brand"] == "KAMAZ"


@pytest.mark.asyncio
async def test_vin_tree(client: AsyncClient):
    """Test VIN tree endpoint."""
    response = await client.get("/api/v1/catalog/vin/XTA6425KLA0000001/tree")
    assert response.status_code == 200
    data = response.json()
    assert "tree" in data
    assert len(data["tree"]) > 0


# ── Health Check ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "работает"


# ── RBAC Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_endpoint_requires_auth(client: AsyncClient):
    """Test that admin endpoints require authentication."""
    response = await client.get("/api/v1/admin/dashboard")
    assert response.status_code == 401  # Unauthorized


@pytest.mark.asyncio
async def test_supplier_endpoint_requires_auth(client: AsyncClient):
    """Test that supplier endpoints require authentication."""
    response = await client.get("/api/v1/supplier/dashboard")
    assert response.status_code == 401  # Unauthorized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
