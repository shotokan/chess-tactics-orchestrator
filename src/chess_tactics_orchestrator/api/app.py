"""
FastAPI application for chess tactics orchestrator.

Provides async REST API for submitting analysis jobs, checking status,
and HITL approval/rejection.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse

from chess_tactics_orchestrator.api.routes import jobs, health
from chess_tactics_orchestrator.infrastructure import get_redis_client, close_redis_client
from chess_tactics_orchestrator.observability import setup_observability, teardown_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup/shutdown for:
    - Redis connection
    - Phoenix observability
    """
    # Startup
    print("🚀 Starting Chess Tactics Orchestrator API...")

    # Setup observability
    setup_observability()

    # Initialize Redis client
    redis = await get_redis_client()
    print(f"✓ Connected to Redis")

    yield

    # Shutdown
    print("🛑 Shutting down...")
    await close_redis_client()
    teardown_observability()
    print("✓ Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title="Chess Tactics Orchestrator API",
    description="Multi-agent system for analyzing Lichess games with LLM-powered insights",
    version="1.0.0",
    lifespan=lifespan
)


# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


# Root endpoint
@app.get("/")
async def root():
    """API root - returns service info."""
    return {
        "service": "Chess Tactics Orchestrator API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }
