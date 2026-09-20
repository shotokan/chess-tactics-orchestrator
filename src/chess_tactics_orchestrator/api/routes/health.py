"""Health check endpoints."""

from fastapi import APIRouter, Depends
from datetime import datetime

from chess_tactics_orchestrator.infrastructure import RedisClient, get_redis_client
from chess_tactics_orchestrator.models import HealthCheckResponse

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(redis: RedisClient = Depends(get_redis_client)):
    """
    Health check endpoint.

    Returns:
        System health status including Redis connectivity and queue length
    """
    try:
        # Test Redis connection
        await redis.client.ping()
        redis_connected = True

        # Get queue length
        queue_length = await redis.get_queue_length()

        status = "healthy"

    except Exception as e:
        redis_connected = False
        queue_length = -1
        status = "unhealthy"

    return HealthCheckResponse(
        status=status,
        redis_connected=redis_connected,
        queue_length=queue_length,
        timestamp=datetime.utcnow()
    )
