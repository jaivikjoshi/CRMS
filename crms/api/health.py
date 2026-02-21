"""Health and metrics endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/metrics")
async def metrics():
    """Basic metrics endpoint for observability."""
    return {"service": "crms", "version": "0.1.0"}
