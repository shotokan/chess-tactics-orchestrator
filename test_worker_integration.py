#!/usr/bin/env python3
"""
Integration test: API + Worker + HITL flow.

Prerequisites:
    Terminal 1: docker-compose up -d
    Terminal 2: ./run_api.sh
    Terminal 3: ./run_worker.sh
    Terminal 4: python test_worker_integration.py
"""

import requests
import time
import sys

BASE_URL = "http://localhost:8000"


def test_full_flow():
    """Test complete API → Worker → HITL → Completion flow."""

    print("=" * 60)
    print("Integration Test: API + Worker + HITL")
    print("=" * 60)

    # Step 1: Create job via API
    print("\n[1/5] Creating job via API...")
    payload = {
        "user_request": "¿cómo me va con la siciliana con negras últimos 5 juegos?",
        "metadata": {"username": "isabido86", "priority": 5}
    }

    response = requests.post(f"{BASE_URL}/api/jobs", json=payload)

    if response.status_code != 202:
        print(f"❌ Failed to create job: {response.status_code}")
        print(response.json())
        sys.exit(1)

    job_id = response.json()["job_id"]
    print(f"✓ Job created: {job_id}")

    # Step 2: Wait for job to reach HITL
    print("\n[2/5] Waiting for worker to process (will stop at HITL)...")
    max_wait = 120  # 2 minutes
    waited = 0
    poll_interval = 3

    while waited < max_wait:
        response = requests.get(f"{BASE_URL}/api/jobs/{job_id}")
        data = response.json()
        status = data["status"]

        print(f"  Status: {status} (waited {waited}s)")

        if status == "waiting_approval":
            print(f"✓ Job reached HITL checkpoint")
            print(f"  Games analyzed: {data.get('result', {}).get('games_analyzed', 0)}")
            break

        if status == "failed":
            print(f"❌ Job failed: {data.get('error')}")
            sys.exit(1)

        time.sleep(poll_interval)
        waited += poll_interval

    if status != "waiting_approval":
        print(f"❌ Job didn't reach HITL in {max_wait}s")
        print(f"   Final status: {status}")
        sys.exit(1)

    # Step 3: Show analysis preview
    print("\n[3/5] Analysis preview:")
    result = data.get("result", {})
    print(f"  Games analyzed: {result.get('games_analyzed', 0)}")

    analysis = result.get("analysis_result", {})
    if analysis:
        metrics = analysis.get("metrics", {})
        print(f"  Winrate: {metrics.get('color_winrates', {}).get('black', {}).get('winrate', 0) * 100:.1f}%")

    # Step 4: Approve job
    print("\n[4/5] Approving job...")
    approval = {
        "approved": True,
        "feedback": "Results look good, continue"
    }

    response = requests.post(
        f"{BASE_URL}/api/jobs/{job_id}/approve",
        json=approval
    )

    if response.status_code != 200:
        print(f"❌ Failed to approve: {response.status_code}")
        print(response.json())
        sys.exit(1)

    print(f"✓ Job approved, worker will resume")

    # Step 5: Wait for completion
    print("\n[5/5] Waiting for completion...")
    waited = 0

    while waited < max_wait:
        response = requests.get(f"{BASE_URL}/api/jobs/{job_id}")
        data = response.json()
        status = data["status"]

        print(f"  Status: {status} (waited {waited}s)")

        if status == "completed":
            print(f"✓ Job completed successfully")

            # Show final answer
            result = data.get("result", {})
            final_answer = result.get("final_answer", "")

            if final_answer:
                print(f"\n📊 Final Answer:")
                print(f"{final_answer[:300]}...")

            break

        if status == "failed":
            print(f"❌ Job failed after approval: {data.get('error')}")
            sys.exit(1)

        time.sleep(poll_interval)
        waited += poll_interval

    if status != "completed":
        print(f"❌ Job didn't complete in {max_wait}s")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ Full integration test passed!")
    print("=" * 60)
    print(f"\nJob ID: {job_id}")
    print(f"Flow: API → Worker → HITL → Approval → Completion")


if __name__ == "__main__":
    print("Integration Test: API + Worker + HITL Flow")
    print("\nPrerequisites:")
    print("  1. docker-compose up -d")
    print("  2. ./run_api.sh (in separate terminal)")
    print("  3. ./run_worker.sh (in separate terminal)")
    print("  4. Wait a few seconds for startup\n")

    input("Press Enter when ready...")

    try:
        test_full_flow()
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API")
        print("Make sure API is running: ./run_api.sh")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
