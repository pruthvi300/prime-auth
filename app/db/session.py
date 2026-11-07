from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create the Async Engine
# The engine is the central connectivity point. 
# 'future=True' enables SQLAlchemy 2.0 style usage.
engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=True, # Logs SQL queries. Set to False in production for performance.
    future=True
)

# Async Session Factory
# This factory generates new Session objects for each request.
# expire_on_commit=False is required for async settings to prevent detached instance errors.
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Dependency Injection for DB Session
# This function is used by FastAPI's Depends() to provide a session to route handlers.
# It uses 'yield' to create a context manager:
# 1. Setup: Creates the session
# 2. Yield: Passes session to the route
# 3. Teardown: Ensures session is closed even if an error occurs
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
