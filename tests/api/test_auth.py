import pytest
from httpx import AsyncClient
from app.core.config import settings

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    response = await client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": "test@example.com",
            "password": "strongpassword123",
            "full_name": "Test User"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "hashed_password" not in data  # Security check

@pytest.mark.asyncio
async def test_create_user_duplicate(client: AsyncClient):
    # Create first user
    await client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": "test@example.com",
            "password": "strongpassword123",
        },
    )
    
    # Try creating same user again
    response = await client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": "test@example.com",
            "password": "password",
        },
    )
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_login_access_token(client: AsyncClient):
    # Setup: Create user
    password = "strongpassword123"
    await client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": "login@example.com",
            "password": password,
        },
    )
    
    # Test Login
    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={
            "username": "login@example.com",
            "password": password,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
