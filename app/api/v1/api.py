"""
Prime Auth - API v1 Router

This module aggregates all v1 API endpoints into a single router.

FastAPI APIRouter (Interview talking point):
- APIRouter is similar to Flask Blueprints
- Groups related endpoints together
- Enables route prefixing and tagging for OpenAPI docs
- Makes testing individual modules easier

Versioning Strategy:
- All routes are under /api/v1
- Future breaking changes go to /api/v2
- This allows gradual client migration
"""

from fastapi import APIRouter
from app.api.v1.endpoints import auth

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

