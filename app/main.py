from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.api import api_router

# Initialize the FastAPI application
# This is the main entry point where the ASGI application is created.
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # Docs are available at /docs (Swagger UI) and /redoc (ReDoc)
)

# Include the API router
# We group routes by version (v1) to allow for future API evolution without breaking changes.
# prefix="/api/v1" means all routes will start with this path.
app.include_router(api_router, prefix=settings.API_V1_STR)

# Root endpoint for health check or welcome message
@app.get("/")
async def root():
    return {"message": "Welcome to Prime Auth Service"}
