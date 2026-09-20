#!/usr/bin/env python3
"""
Test FastAPI endpoints manually.

Prerequisites:
    docker-compose up -d redis
    # In another terminal:
    uvicorn chess_tactics_orchestrator.api.app:app --reload
"""

import requests
import time

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("=" * 60)
    print("Test 1: Health Check")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["redis_connected"] is True
    print("✓ Health check passed\n")


def test_create_job():
    """Test job creation."""
    print("=" * 60)
    print("Test 2: Create Job")
    print("=" * 60)

    payload = {
        "user_request": "¿cómo me va con la siciliana con negras?",
        "metadata": {
            "username": "isabido86",
            "priority": 5
        }
    }

    response = requests.post(f"{BASE_URL}/api/jobs", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert "job_id" in data

    job_id = data["job_id"]
    print(f"✓ Job created: {job_id}\n")

    return job_id


def test_get_job_status(job_id):
    """Test job status retrieval."""
    print("=" * 60)
    print("Test 3: Get Job Status")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/jobs/{job_id}")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    print("✓ Job status retrieved\n")


def test_approval_flow(job_id):
    """Test HITL approval (simulated)."""
    print("=" * 60)
    print("Test 4: HITL Approval")
    print("=" * 60)

    # Wait for job to reach waiting_approval status
    print("Waiting for job to reach HITL checkpoint...")
    max_wait = 60
    waited = 0

    while waited < max_wait:
        response = requests.get(f"{BASE_URL}/api/jobs/{job_id}")
        data = response.json()

        if data["status"] == "waiting_approval":
            print(f"✓ Job reached HITL checkpoint")
            break

        time.sleep(2)
        waited += 2
        print(f"  Status: {data['status']} (waited {waited}s)")

    if data["status"] != "waiting_approval":
        print(f"⚠️  Job didn't reach HITL in {max_wait}s (status: {data['status']})")
        return

    # Approve job
    print("\nApproving job...")
    approval_payload = {
        "approved": True,
        "feedback": "Results look good"
    }

    response = requests.post(
        f"{BASE_URL}/api/jobs/{job_id}/approve",
        json=approval_payload
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    print("✓ Job approved\n")


def test_invalid_job():
    """Test 404 for non-existent job."""
    print("=" * 60)
    print("Test 5: Invalid Job ID")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/jobs/invalid-job-id")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    assert response.status_code == 404
    print("✓ 404 handled correctly\n")


if __name__ == "__main__":
    print("Testing FastAPI Endpoints")
    print("Make sure API is running: uvicorn chess_tactics_orchestrator.api.app:app\n")

    try:
        test_health()
        job_id = test_create_job()
        test_get_job_status(job_id)
        # test_approval_flow(job_id)  # Requires worker running
        test_invalid_job()

        print("=" * 60)
        print("✅ All basic tests passed!")
        print("=" * 60)
        print("\nNote: HITL approval test requires background worker")
        print("To test full flow:")
        print("  1. Start worker: python -m chess_tactics_orchestrator.worker")
        print("  2. Run test_approval_flow()")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API")
        print("Start server: uvicorn chess_tactics_orchestrator.api.app:app --reload")
