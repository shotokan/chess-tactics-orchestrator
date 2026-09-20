#!/usr/bin/env python3
"""
Test Redis connection and basic operations.

Prerequisites:
    docker-compose up -d redis

Usage:
    uv run test_redis_connection.py
"""

import asyncio
import sys
from datetime import datetime

sys.path.insert(0, 'src')

from chess_tactics_orchestrator.infrastructure.redis_client import RedisClient
from chess_tactics_orchestrator.models.job import generate_job_id


async def test_redis_connection():
    """Test basic Redis operations."""

    print("=" * 60)
    print("Testing Redis Connection and Operations")
    print("=" * 60)

    redis = RedisClient(host="localhost", port=6379)

    try:
        # 1. Test connection
        print("\n[1/6] Testing connection...")
        await redis.connect()
        print("✓ Connected to Redis successfully")

        # 2. Test ping
        print("\n[2/6] Testing ping...")
        pong = await redis.client.ping()
        print(f"✓ Ping response: {pong}")

        # 3. Test job enqueue
        print("\n[3/6] Testing job enqueue...")
        job_id = generate_job_id()
        await redis.enqueue_job(
            job_id=job_id,
            user_request="¿cómo me va con la siciliana con negras?",
            metadata={"username": "isabido86", "priority": 5}
        )
        print(f"✓ Enqueued job: {job_id}")

        # 4. Test job status retrieval
        print("\n[4/6] Testing job status retrieval...")
        job_status = await redis.get_job_status(job_id)
        print(f"✓ Job status: {job_status['status']}")
        print(f"  Created at: {job_status['created_at']}")
        print(f"  User request: {job_status['user_request']}")
        print(f"  Metadata: {job_status['metadata']}")

        # 5. Test job status update
        print("\n[5/6] Testing job status update...")
        await redis.update_job_status(
            job_id=job_id,
            status="processing"
        )
        updated_status = await redis.get_job_status(job_id)
        print(f"✓ Updated status: {updated_status['status']}")
        print(f"  Updated at: {updated_status['updated_at']}")

        # 6. Test checkpoint operations
        print("\n[6/6] Testing checkpoint save/retrieve...")
        checkpoint_id = "checkpoint_001"
        test_state = {
            "user_request": "test query",
            "games_raw": [],
            "contributions": [],
            "refinement_count": 0
        }

        await redis.save_checkpoint(
            thread_id=job_id,
            checkpoint_id=checkpoint_id,
            state=test_state
        )
        print(f"✓ Saved checkpoint: {checkpoint_id}")

        retrieved_state = await redis.get_checkpoint(
            thread_id=job_id,
            checkpoint_id=checkpoint_id
        )
        print(f"✓ Retrieved checkpoint: {retrieved_state is not None}")
        print(f"  State matches: {retrieved_state == test_state}")

        # 7. Test queue operations
        print("\n[7/7] Testing queue operations...")
        queue_length = await redis.get_queue_length()
        print(f"✓ Current queue length: {queue_length}")

        # Dequeue the job we created
        dequeued_job_id = await redis.dequeue_job(timeout=1)
        print(f"✓ Dequeued job: {dequeued_job_id}")
        print(f"  Matches enqueued job: {dequeued_job_id == job_id}")

        new_queue_length = await redis.get_queue_length()
        print(f"✓ Queue length after dequeue: {new_queue_length}")

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await redis.disconnect()
        print("\n✓ Disconnected from Redis")


if __name__ == "__main__":
    asyncio.run(test_redis_connection())
