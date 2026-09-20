"""
Job state models for API and Redis persistence.

Defines Pydantic models for job lifecycle management across the async API.
"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


JobStatus = Literal["queued", "processing", "waiting_approval", "completed", "failed"]


class JobMetadata(BaseModel):
    """
    Optional metadata attached to a job.

    Attributes:
        username: Lichess username (if provided)
        priority: Job priority (higher = process first)
        user_id: External user identifier
        tags: Arbitrary tags for filtering/grouping
    """
    username: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=10)
    user_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class JobCreateRequest(BaseModel):
    """
    Request payload for creating a new analysis job.

    Example:
        {
            "user_request": "¿cómo me va con la siciliana con negras?",
            "metadata": {
                "username": "isabido86",
                "priority": 5
            }
        }
    """
    user_request: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Natural language query in Spanish or English"
    )
    metadata: Optional[JobMetadata] = None


class JobResponse(BaseModel):
    """
    Response returned when creating or querying a job.

    Attributes:
        job_id: Unique job identifier
        status: Current job status
        user_request: Original user query
        created_at: Job creation timestamp
        updated_at: Last status update timestamp
        result: Analysis result (only present when status=completed)
        error: Error message (only present when status=failed)
        metadata: Job metadata
    """
    job_id: str
    status: JobStatus
    user_request: str
    created_at: datetime
    updated_at: datetime
    result: Optional[dict] = None
    error: Optional[str] = None
    metadata: Optional[JobMetadata] = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "user_request": "¿cómo me va con la siciliana con negras?",
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:32:45Z",
                "result": {
                    "final_answer": "Analizadas 94 partidas...",
                    "metrics": {
                        "overall_winrate": 0.606,
                        "games_analyzed": 20
                    }
                },
                "metadata": {
                    "username": "isabido86",
                    "priority": 5
                }
            }
        }


class JobApprovalRequest(BaseModel):
    """
    Request payload for Human-in-the-Loop approval.

    Example:
        {
            "approved": true,
            "feedback": "Looks good, continue"
        }
    """
    approved: bool
    feedback: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional feedback for refinement (if not approved)"
    )


class JobApprovalResponse(BaseModel):
    """
    Response after approval/rejection action.

    Attributes:
        job_id: Job identifier
        status: New status (processing if approved, waiting_approval if rejected)
        message: Human-readable confirmation message
    """
    job_id: str
    status: JobStatus
    message: str


class HealthCheckResponse(BaseModel):
    """
    Health check response for monitoring.

    Attributes:
        status: Overall health status
        redis_connected: Redis connection status
        queue_length: Current number of queued jobs
        timestamp: Health check timestamp
    """
    status: Literal["healthy", "degraded", "unhealthy"]
    redis_connected: bool
    queue_length: int
    timestamp: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "redis_connected": True,
                "queue_length": 3,
                "timestamp": "2025-01-15T10:30:00Z"
            }
        }


class JobListResponse(BaseModel):
    """
    Response for listing jobs with pagination.

    Attributes:
        jobs: List of job summaries
        total: Total number of jobs matching filter
        page: Current page number
        page_size: Number of jobs per page
    """
    jobs: list[JobResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


def generate_job_id() -> str:
    """Generate a unique job ID (UUID4)."""
    return str(uuid4())
