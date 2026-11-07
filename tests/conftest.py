import os

# Configure the app for tests before anything imports app settings.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("BCRYPT_ROUNDS", "4")  # fast hashing in tests

from collections.abc import AsyncIterator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

API = "/api/v1"


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    # StaticPool keeps one connection so the in-memory database survives across sessions.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def register(client: AsyncClient, email: str = "user@example.com", password: str = "strongpassword123"):
    return await client.post(f"{API}/auth/register", json={"email": email, "password": password})


async def login(client: AsyncClient, email: str = "user@example.com", password: str = "strongpassword123"):
    return await client.post(f"{API}/auth/login", data={"username": email, "password": password})
