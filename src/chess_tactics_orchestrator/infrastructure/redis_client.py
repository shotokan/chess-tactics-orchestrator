"""
Async Redis client for job queue and state management.

Provides connection pooling, job state management, and checkpoint storage for LangGraph.
"""

import os
import json
from typing import Optional, Any
from datetime import datetime, timedelta
import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool


class RedisClient:
    """
    Async Redis client for managing job state and LangGraph checkpoints.

    Handles:
    - Job queue operations (enqueue, dequeue, status updates)
    - LangGraph checkpoint persistence
    - TTL-based cleanup for completed jobs
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        max_connections: int = 10,
        decode_responses: bool = True
    ):
        """
        Initialize Redis client with connection pool.

        Args:
            host: Redis host (default: localhost)
            port: Redis port (default: 6379)
            db: Redis database number (default: 0)
            max_connections: Max connections in pool (default: 10)
            decode_responses: Auto-decode bytes to str (default: True)
        """
        self.pool = ConnectionPool(
            host=host,
            port=port,
            db=db,
            max_connections=max_connections,
            decode_responses=decode_responses
        )
        self._client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection from pool."""
        if self._client is None:
            self._client = aioredis.Redis(connection_pool=self.pool)
            # Test connection
            await self._client.ping()

    async def disconnect(self) -> None:
        """Close Redis connection and pool."""
        if self._client:
            await self._client.close()
            await self.pool.disconnect()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        """Get Redis client instance (must call connect() first)."""
        if self._client is None:
            raise RuntimeError("RedisClient not connected. Call connect() first.")
        return self._client

    # Job Queue Operations

    async def enqueue_job(
        self,
        job_id: str,
        user_request: str,
        metadata: Optional[dict] = None
    ) -> None:
        """
        Enqueue a new analysis job.

        Args:
            job_id: Unique job identifier (UUID recommended)
            user_request: User's natural language query
            metadata: Optional metadata (username, priority, etc.)
        """
        job_data = {
            "job_id": job_id,
            "user_request": user_request,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        # Store job state as hash
        await self.client.hset(
            f"job:{job_id}",
            mapping={k: json.dumps(v) if isinstance(v, dict) else v for k, v in job_data.items()}
        )

        # Add to queue (FIFO with RPUSH/LPOP)
        await self.client.rpush("job_queue", job_id)

        # Set TTL for job data (7 days)
        await self.client.expire(f"job:{job_id}", 7 * 24 * 60 * 60)

    async def dequeue_job(self, timeout: int = 0) -> Optional[str]:
        """
        Dequeue next job from queue (blocking operation).

        Args:
            timeout: Block for N seconds (0 = block forever)

        Returns:
            job_id if available, None if timeout
        """
        result = await self.client.blpop("job_queue", timeout=timeout)
        if result:
            _, job_id = result  # blpop returns (key, value)
            return job_id
        return None

    async def get_job_status(self, job_id: str) -> Optional[dict]:
        """
        Retrieve current job state.

        Args:
            job_id: Job identifier

        Returns:
            Job data dict or None if not found
        """
        data = await self.client.hgetall(f"job:{job_id}")
        if not data:
            return None

        # Deserialize JSON fields
        for key in ["metadata", "result", "error"]:
            if key in data and data[key]:
                try:
                    data[key] = json.loads(data[key])
                except json.JSONDecodeError:
                    pass

        return data

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Update job status and optionally store result/error.

        Args:
            job_id: Job identifier
            status: New status (processing, completed, failed, waiting_approval)
            result: Final result dict (for completed jobs)
            error: Error message (for failed jobs)
        """
        updates = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }

        if result is not None:
            updates["result"] = json.dumps(result)

        if error is not None:
            updates["error"] = error

        await self.client.hset(f"job:{job_id}", mapping=updates)

    # LangGraph Checkpoint Operations

    async def save_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
        state: dict
    ) -> None:
        """
        Save LangGraph checkpoint for resumable execution.

        Args:
            thread_id: Thread identifier (maps to job_id)
            checkpoint_id: Unique checkpoint identifier
            state: Serialized AgentState
        """
        key = f"checkpoint:{thread_id}:{checkpoint_id}"
        await self.client.set(
            key,
            json.dumps(state),
            ex=7 * 24 * 60 * 60  # 7 day TTL
        )

        # Track checkpoint in sorted set (by timestamp)
        await self.client.zadd(
            f"checkpoints:{thread_id}",
            {checkpoint_id: datetime.utcnow().timestamp()}
        )

    async def get_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[dict]:
        """
        Retrieve checkpoint state.

        Args:
            thread_id: Thread identifier
            checkpoint_id: Specific checkpoint (None = latest)

        Returns:
            Deserialized state dict or None
        """
        if checkpoint_id is None:
            # Get latest checkpoint
            latest = await self.client.zrevrange(
                f"checkpoints:{thread_id}",
                0,
                0
            )
            if not latest:
                return None
            checkpoint_id = latest[0]

        key = f"checkpoint:{thread_id}:{checkpoint_id}"
        data = await self.client.get(key)

        if data:
            return json.loads(data)
        return None

    async def list_checkpoints(self, thread_id: str) -> list[str]:
        """
        List all checkpoint IDs for a thread (newest first).

        Args:
            thread_id: Thread identifier

        Returns:
            List of checkpoint IDs
        """
        return await self.client.zrevrange(f"checkpoints:{thread_id}", 0, -1)

    # Utility Methods

    async def cleanup_old_jobs(self, days: int = 7) -> int:
        """
        Remove jobs older than N days (manual cleanup).

        Args:
            days: Age threshold in days

        Returns:
            Number of jobs deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Scan for job keys
        deleted = 0
        async for key in self.client.scan_iter(match="job:*"):
            created_str = await self.client.hget(key, "created_at")
            if created_str:
                created = datetime.fromisoformat(created_str)
                if created < cutoff:
                    await self.client.delete(key)
                    deleted += 1

        return deleted

    async def get_queue_length(self) -> int:
        """Get current number of queued jobs."""
        return await self.client.llen("job_queue")


# Singleton factory for FastAPI dependency injection
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """
    Get shared Redis client instance (FastAPI dependency).

    Usage:
        @app.get("/status/{job_id}")
        async def get_status(
            job_id: str,
            redis: RedisClient = Depends(get_redis_client)
        ):
            return await redis.get_job_status(job_id)
    """
    global _redis_client

    if _redis_client is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))

        _redis_client = RedisClient(host=host, port=port)
        await _redis_client.connect()

    return _redis_client


async def close_redis_client() -> None:
    """Close shared Redis client (call on app shutdown)."""
    global _redis_client

    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None
