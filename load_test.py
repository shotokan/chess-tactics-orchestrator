#!/usr/bin/env python3
"""
Load test: 5 concurrent analysis requests.

Captures metrics:
- Total latency (end-to-end)
- HITL wait time
- Completion time
- Phoenix traces for cost analysis

Prerequisites:
    docker-compose up -d
    ./run_api.sh
    ./run_worker.sh
"""

import asyncio
import aiohttp
import time
from datetime import datetime
import json

BASE_URL = "http://localhost:8000"


class LoadTester:
    """Load tester for concurrent job processing."""

    def __init__(self, num_concurrent=5):
        """
        Initialize load tester.

        Args:
            num_concurrent: Number of concurrent requests
        """
        self.num_concurrent = num_concurrent
        self.results = []

    async def create_job(self, session, job_num):
        """Create single job via API."""
        payload = {
            "user_request": f"¿cómo me va con la siciliana con negras últimos {5 + job_num} juegos?",
            "metadata": {
                "username": "isabido86",
                "priority": 5,
                "test_id": job_num
            }
        }

        async with session.post(f"{BASE_URL}/api/jobs", json=payload) as resp:
            data = await resp.json()
            return data["job_id"]

    async def poll_until_status(self, session, job_id, target_status, timeout=180):
        """
        Poll job until reaches target status.

        Returns:
            (success, elapsed_seconds)
        """
        start = time.time()

        while (time.time() - start) < timeout:
            async with session.get(f"{BASE_URL}/api/jobs/{job_id}") as resp:
                data = await resp.json()
                status = data["status"]

                if status == target_status:
                    return True, time.time() - start

                if status == "failed":
                    return False, time.time() - start

            await asyncio.sleep(2)

        return False, time.time() - start

    async def approve_job(self, session, job_id):
        """Approve HITL checkpoint."""
        payload = {"approved": True, "feedback": "Load test approval"}

        async with session.post(f"{BASE_URL}/api/jobs/{job_id}/approve", json=payload) as resp:
            return resp.status == 200

    async def run_single_job(self, session, job_num):
        """
        Run complete job lifecycle.

        Returns:
            Metrics dict
        """
        print(f"\n[Job {job_num}] Starting...")

        metrics = {
            "job_num": job_num,
            "job_id": None,
            "total_latency": 0,
            "hitl_latency": 0,
            "completion_latency": 0,
            "success": False,
            "error": None
        }

        start_total = time.time()

        try:
            # Create job
            job_id = await self.create_job(session, job_num)
            metrics["job_id"] = job_id
            print(f"[Job {job_num}] Created: {job_id}")

            # Wait for HITL
            start_hitl = time.time()
            success, elapsed = await self.poll_until_status(
                session, job_id, "waiting_approval", timeout=120
            )

            if not success:
                metrics["error"] = "Did not reach HITL"
                print(f"[Job {job_num}] ❌ Failed to reach HITL")
                return metrics

            metrics["hitl_latency"] = elapsed
            print(f"[Job {job_num}] ⏸️  HITL reached ({elapsed:.1f}s)")

            # Approve
            approved = await self.approve_job(session, job_id)
            if not approved:
                metrics["error"] = "Approval failed"
                return metrics

            print(f"[Job {job_num}] ✓ Approved")

            # Wait for completion
            start_completion = time.time()
            success, elapsed = await self.poll_until_status(
                session, job_id, "completed", timeout=60
            )

            if not success:
                metrics["error"] = "Did not complete"
                print(f"[Job {job_num}] ❌ Failed to complete")
                return metrics

            metrics["completion_latency"] = elapsed
            metrics["total_latency"] = time.time() - start_total
            metrics["success"] = True

            print(f"[Job {job_num}] ✅ Completed ({metrics['total_latency']:.1f}s total)")

        except Exception as e:
            metrics["error"] = str(e)
            print(f"[Job {job_num}] ❌ Exception: {e}")

        return metrics

    async def run_concurrent_jobs(self):
        """Run N concurrent jobs."""
        print("=" * 60)
        print(f"Load Test: {self.num_concurrent} Concurrent Jobs")
        print("=" * 60)

        async with aiohttp.ClientSession() as session:
            # Launch concurrent jobs
            tasks = [
                self.run_single_job(session, i)
                for i in range(1, self.num_concurrent + 1)
            ]

            # Wait for all to complete
            self.results = await asyncio.gather(*tasks)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("Load Test Results")
        print("=" * 60)

        successful = [r for r in self.results if r["success"]]
        failed = [r for r in self.results if not r["success"]]

        print(f"\nSuccess: {len(successful)}/{self.num_concurrent}")
        print(f"Failed: {len(failed)}/{self.num_concurrent}")

        if successful:
            avg_total = sum(r["total_latency"] for r in successful) / len(successful)
            avg_hitl = sum(r["hitl_latency"] for r in successful) / len(successful)
            avg_completion = sum(r["completion_latency"] for r in successful) / len(successful)

            print(f"\nLatency (average):")
            print(f"  Total: {avg_total:.1f}s")
            print(f"  To HITL: {avg_hitl:.1f}s")
            print(f"  After approval: {avg_completion:.1f}s")

            print(f"\nLatency (min/max):")
            print(f"  Total: {min(r['total_latency'] for r in successful):.1f}s / {max(r['total_latency'] for r in successful):.1f}s")

        if failed:
            print(f"\nFailed jobs:")
            for r in failed:
                print(f"  Job {r['job_num']}: {r['error']}")

        # Save detailed results
        with open("load_test_results.json", "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\n✓ Detailed results saved to: load_test_results.json")

        print("\n" + "=" * 60)
        print("Phoenix Dashboard")
        print("=" * 60)
        print("View traces: http://localhost:6006")
        print("  - Filter by project: chess-tactics-orchestrator")
        print("  - View latency per agent")
        print("  - View LLM token usage for cost estimation")
        print("=" * 60)


async def main():
    """Main entry point."""
    print("Load Test - Chess Tactics Orchestrator")
    print("\nPrerequisites:")
    print("  1. docker-compose up -d")
    print("  2. ./run_api.sh (Terminal 2)")
    print("  3. ./run_worker.sh (Terminal 3)")
    print("  4. Wait ~10s for startup\n")

    input("Press Enter when ready...")

    tester = LoadTester(num_concurrent=5)
    await tester.run_concurrent_jobs()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
