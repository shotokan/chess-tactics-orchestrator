"""
Background worker for processing analysis jobs.

Continuously polls Redis queue, processes jobs through LangGraph,
handles HITL interrupts, and updates job status.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

from chess_tactics_orchestrator.graph import create_graph
from chess_tactics_orchestrator.infrastructure import (
    RedisClient,
    create_redis_checkpointer,
)
from chess_tactics_orchestrator.observability import (
    setup_observability,
    teardown_observability,
    get_phoenix_tracer,
)

load_dotenv()


class JobWorker:
    """
    Background worker for processing chess analysis jobs.

    Handles:
    - Polling Redis queue for jobs
    - Running LangGraph with checkpointing
    - Detecting HITL interrupts
    - Updating job status in Redis
    """

    def __init__(self):
        """Initialize worker with Redis and graph."""
        self.redis = RedisClient(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379"))
        )

        # Create checkpointer for graph
        self.checkpointer = create_redis_checkpointer()

        # Create graph with checkpointing
        self.graph = create_graph(checkpointer=self.checkpointer)

        print("✓ Worker initialized")

    async def start(self):
        """Start worker loop."""
        print("🚀 Starting job worker...")
        print("  Polling queue: job_queue")
        print("  Press Ctrl+C to stop\n")

        # Connect to Redis
        await self.redis.connect()

        try:
            while True:
                await self.process_next_job()

        except KeyboardInterrupt:
            print("\n🛑 Shutting down worker...")
        finally:
            await self.redis.disconnect()
            print("✓ Worker stopped")

    async def process_next_job(self):
        """
        Poll queue and process next job.

        Blocks for up to 1 second waiting for job.
        """
        # Blocking dequeue with 1s timeout (short to handle Ctrl+C gracefully)
        job_id = await self.redis.dequeue_job(timeout=1)

        if not job_id:
            # No jobs in queue, continue polling
            return

        print(f"\n{'='*60}")
        print(f"📋 Processing job: {job_id}")
        print(f"{'='*60}")

        phoenix = get_phoenix_tracer()

        with phoenix.span("worker_process_job", {"job_id": job_id}):
            try:
                # Update status to processing
                await self.redis.update_job_status(job_id, status="processing")

                # Get job data
                job_data = await self.redis.get_job_status(job_id)
                user_request = job_data["user_request"]

                print(f"  Request: {user_request}")

                # Run graph with checkpointing
                result = await self.run_graph(job_id, user_request)

                # Check if interrupted at HITL
                if result.get("_interrupted"):
                    print(f"  ⏸️  Interrupted at HITL checkpoint")
                    await self.redis.update_job_status(
                        job_id,
                        status="waiting_approval",
                        result={
                            "analysis_result": result.get("analysis_result"),
                            "analysis_metadata": result.get("analysis_metadata"),
                            "games_analyzed": len(result.get("games_raw", [])),
                        }
                    )
                    print(f"  Status: waiting_approval")
                    return

                # Completed successfully
                print(f"  ✓ Completed")
                await self.redis.update_job_status(
                    job_id,
                    status="completed",
                    result={
                        "final_answer": result.get("final_answer"),
                        "analysis_result": result.get("analysis_result"),
                        "contributions": result.get("contributions", []),
                    }
                )
                print(f"  Status: completed")

            except Exception as e:
                print(f"  ❌ Failed: {e}")

                # Update status to failed
                await self.redis.update_job_status(
                    job_id,
                    status="failed",
                    error=str(e)
                )

                import traceback
                traceback.print_exc()

    async def run_graph(self, job_id: str, user_request: str) -> dict:
        """
        Run LangGraph for job with checkpointing.

        Args:
            job_id: Job identifier (used as thread_id)
            user_request: User's natural language query

        Returns:
            Final state from graph execution
        """
        # Check if resuming from checkpoint (sync method in thread)
        checkpoint = await asyncio.to_thread(
            self.checkpointer.get,
            {"configurable": {"thread_id": job_id}}
        )

        if checkpoint:
            print(f"  🔄 Resuming from checkpoint")

            # Get job data to check for approval
            job_data = await self.redis.get_job_status(job_id)
            result = job_data.get("result", {})

            # Resume with approval decision
            resume_state = {
                "hitl_approved": result.get("hitl_approved", False),
                "hitl_feedback": result.get("hitl_feedback"),
                "needs_refinement": result.get("needs_refinement", False),
            }

            # Invoke graph with resume state
            final_state = await asyncio.to_thread(
                self.graph.invoke,
                resume_state,
                {"configurable": {"thread_id": job_id}}
            )

        else:
            print(f"  ▶️  Starting new execution")

            # Initial state
            initial_state = {
                "user_request": user_request,
                "games_raw": [],
                "contributions": [],
                "analysis_result": None,
                "analysis_metadata": {},
                "needs_refinement": False,
                "refine_target": None,
                "refinement_count": 0,
                "final_answer": None,
                "hitl_approved": False,
                "hitl_feedback": None,
            }

            # Invoke graph
            final_state = await asyncio.to_thread(
                self.graph.invoke,
                initial_state,
                {"configurable": {"thread_id": job_id}}
            )

        return final_state


async def main():
    """Main entry point for worker."""

    # Setup observability
    setup_observability()

    # Create and start worker
    worker = JobWorker()

    try:
        await worker.start()
    finally:
        teardown_observability()


if __name__ == "__main__":
    asyncio.run(main())
