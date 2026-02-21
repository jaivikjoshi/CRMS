"""CRMS FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crms.api.admin import router as admin_router
from crms.api.evaluations import router as evaluations_router
from crms.api.health import router as health_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CRMS - Compliance Rules Microservice",
    description="Evaluates compliance/tax rules for transactions with versioned rulesets",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["Health"])
app.include_router(evaluations_router, prefix="/v1", tags=["Evaluations"])
app.include_router(admin_router, prefix="/v1/admin", tags=["Admin"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "CRMS", "version": "0.1.0", "docs": "/docs"}
