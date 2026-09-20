"""
LangGraph checkpoint management with RedisSaver.

Provides factory functions for creating and configuring RedisSaver instances
for LangGraph state persistence.
"""

import os
from typing import Optional
from langgraph.checkpoint.redis import RedisSaver
from redis.asyncio import ConnectionPool


def create_redis_checkpointer(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0
) -> RedisSaver:
    """
    Create RedisSaver for LangGraph checkpoints.

    Args:
        host: Redis host (default: localhost)
        port: Redis port (default: 6379)
        db: Redis database number (default: 0)

    Returns:
        RedisSaver instance for use with graph.compile(checkpointer=...)

    Usage:
        checkpointer = create_redis_checkpointer()
        graph = create_graph(checkpointer=checkpointer)

        # Run with thread_id for checkpoint persistence
        result = graph.invoke(state, config={"configurable": {"thread_id": job_id}})

        # Resume from checkpoint
        result = graph.invoke(None, config={"configurable": {"thread_id": job_id}})
    """
    # Create Redis URL for RedisSaver
    redis_url = f"redis://{host}:{port}/{db}"

    # Create RedisSaver with redis_url parameter
    saver = RedisSaver(redis_url=redis_url)

    return saver


def get_redis_checkpointer() -> Optional[RedisSaver]:
    """
    Get RedisSaver configured from environment variables.

    Environment variables:
        REDIS_HOST: Redis host (default: localhost)
        REDIS_PORT: Redis port (default: 6379)
        REDIS_DB: Redis database (default: 0)
        CHECKPOINT_ENABLED: Enable checkpointing (default: true)

    Returns:
        RedisSaver if enabled, None otherwise
    """
    if os.getenv("CHECKPOINT_ENABLED", "true").lower() != "true":
        return None

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))

    return create_redis_checkpointer(host=host, port=port, db=db)
