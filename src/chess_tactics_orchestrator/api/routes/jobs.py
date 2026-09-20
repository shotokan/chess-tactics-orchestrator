"""Job management endpoints for analysis requests."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from datetime import datetime

from chess_tactics_orchestrator.infrastructure import RedisClient, get_redis_client
from chess_tactics_orchestrator.models import (
    JobCreateRequest,
    JobResponse,
    JobApprovalRequest,
    JobApprovalResponse,
    generate_job_id,
)

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=202)
async def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    redis: RedisClient = Depends(get_redis_client)
):
    """
    Create new analysis job.

    Enqueues job for background processing. Worker will:
    1. Fetch games from Lichess
    2. Analyze with LLM + Stockfish
    3. Pause at HITL checkpoint for approval

    Args:
        request: Job creation request with user query
        background_tasks: FastAPI background tasks
        redis: Redis client

    Returns:
        Job response with job_id and status="queued"
    """
    # Generate unique job ID
    job_id = generate_job_id()

    # Enqueue job in Redis
    await redis.enqueue_job(
        job_id=job_id,
        user_request=request.user_request,
        metadata=request.metadata.dict() if request.metadata else None
    )

    # Return immediately (job processed by worker)
    job_data = await redis.get_job_status(job_id)

    return JobResponse(
        job_id=job_id,
        status=job_data["status"],
        user_request=job_data["user_request"],
        created_at=datetime.fromisoformat(job_data["created_at"]),
        updated_at=datetime.fromisoformat(job_data["created_at"]),
        metadata=request.metadata
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    redis: RedisClient = Depends(get_redis_client)
):
    """
    Get job status and results.

    Returns current state of job including:
    - Status (queued, processing, waiting_approval, completed, failed)
    - Analysis results (if completed or waiting approval)
    - Error message (if failed)

    Args:
        job_id: Job identifier

    Returns:
        Job response with current status and results
    """
    job_data = await redis.get_job_status(job_id)

    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobResponse(
        job_id=job_id,
        status=job_data["status"],
        user_request=job_data["user_request"],
        created_at=datetime.fromisoformat(job_data["created_at"]),
        updated_at=datetime.fromisoformat(job_data["updated_at"]),
        result=job_data.get("result"),
        error=job_data.get("error"),
        metadata=job_data.get("metadata")
    )


@router.post("/{job_id}/approve", response_model=JobApprovalResponse)
async def approve_job(
    job_id: str,
    request: JobApprovalRequest,
    redis: RedisClient = Depends(get_redis_client)
):
    """
    Approve or reject HITL checkpoint.

    When job reaches HITL checkpoint (status=waiting_approval):
    - Approve: Job continues to completion
    - Reject: Job refines analysis based on feedback

    Args:
        job_id: Job identifier
        request: Approval decision + optional feedback

    Returns:
        Updated job status after approval/rejection
    """
    # Get current job
    job_data = await redis.get_job_status(job_id)

    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job_data["status"] != "waiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} not waiting for approval (status: {job_data['status']})"
        )

    # Update job with approval decision
    if request.approved:
        # Mark approved - worker will resume to completion
        await redis.update_job_status(
            job_id=job_id,
            status="processing",
            result={"hitl_approved": True, "hitl_feedback": request.feedback}
        )

        return JobApprovalResponse(
            job_id=job_id,
            status="processing",
            message="Job approved - resuming to completion"
        )
    else:
        # Mark rejected - worker will refine
        await redis.update_job_status(
            job_id=job_id,
            status="processing",
            result={
                "hitl_approved": False,
                "hitl_feedback": request.feedback or "Rejected by user",
                "needs_refinement": True
            }
        )

        return JobApprovalResponse(
            job_id=job_id,
            status="processing",
            message=f"Job rejected - will refine based on feedback: {request.feedback}"
        )


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    redis: RedisClient = Depends(get_redis_client)
):
    """
    Cancel/delete job.

    Removes job from queue or marks as cancelled if already processing.

    Args:
        job_id: Job identifier
    """
    job_data = await redis.get_job_status(job_id)

    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Mark as cancelled
    await redis.update_job_status(job_id=job_id, status="cancelled")

    return None


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    status: str = None,
    limit: int = 50,
    redis: RedisClient = Depends(get_redis_client)
):
    """
    List all jobs (with optional status filter).

    Args:
        status: Optional status filter (queued, processing, etc.)
        limit: Max number of jobs to return

    Returns:
        List of job responses
    """
    # TODO: Implement job listing with Redis SCAN
    # For now, return empty list
    return []
