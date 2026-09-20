#!/usr/bin/env python3
"""
Test complete HITL flow with checkpoint persistence.

Simulates:
1. Initial analysis run → stops at HITL
2. Human approval → resumes to completion
3. Human rejection → refines and re-analyzes
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, 'src')

from chess_tactics_orchestrator.graph import create_graph
from chess_tactics_orchestrator.infrastructure import create_redis_checkpointer


def test_hitl_approval_flow():
    """Test HITL with approval."""

    print("=" * 60)
    print("Test 1: HITL Approval Flow")
    print("=" * 60)

    # Setup
    checkpointer = create_redis_checkpointer()
    graph = create_graph(checkpointer=checkpointer)
    thread_id = "hitl_test_approval_001"

    initial_state = {
        "user_request": "¿cómo me va con la siciliana con negras últimos 5 juegos?",
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

    config = {"configurable": {"thread_id": thread_id}}

    # Step 1: Run until HITL checkpoint
    print("\n[Step 1/3] Running analysis (will stop at HITL)...")
    try:
        result = graph.invoke(initial_state, config=config)

        print(f"✓ Stopped at HITL checkpoint")
        print(f"  Games: {len(result.get('games_raw', []))}")
        print(f"  Analysis: {'Present' if result.get('analysis_result') else 'None'}")
        print(f"  HITL approved: {result.get('hitl_approved')}")

        # Step 2: Simulate human approval
        print("\n[Step 2/3] Human approves results...")
        approved_state = {**result, "hitl_approved": True}

        # Step 3: Resume from checkpoint
        print("\n[Step 3/3] Resuming with approval...")
        final = graph.invoke(approved_state, config=config)

        print(f"\n✓ Completed successfully")
        print(f"  Final answer: {'Present' if final.get('final_answer') else 'None'}")
        print(f"  Contributions: {len(final.get('contributions', []))}")

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hitl_rejection_flow():
    """Test HITL with rejection and refinement."""

    print("\n\n" + "=" * 60)
    print("Test 2: HITL Rejection + Refinement Flow")
    print("=" * 60)

    # Setup
    checkpointer = create_redis_checkpointer()
    graph = create_graph(checkpointer=checkpointer)
    thread_id = "hitl_test_rejection_002"

    initial_state = {
        "user_request": "¿cómo me va con la siciliana con negras últimos 3 juegos?",
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

    config = {"configurable": {"thread_id": thread_id}}

    # Step 1: Run until HITL checkpoint
    print("\n[Step 1/4] Running analysis (will stop at HITL)...")
    try:
        result = graph.invoke(initial_state, config=config)

        print(f"✓ Stopped at HITL checkpoint")
        games_count = len(result.get('games_raw', []))
        print(f"  Games: {games_count}")

        # Step 2: Simulate human rejection
        print("\n[Step 2/4] Human rejects (wants more games)...")
        rejected_state = {
            **result,
            "hitl_approved": False,
            "hitl_feedback": "Need at least 10 games",
            "needs_refinement": True,
            "refine_target": "research",
            "refinement_count": result.get("refinement_count", 0) + 1
        }

        # Step 3: Resume with rejection → should refine
        print("\n[Step 3/4] Resuming with rejection (will refine research)...")
        refined = graph.invoke(rejected_state, config=config)

        print(f"✓ Refinement completed")
        print(f"  New games count: {len(refined.get('games_raw', []))}")

        # Step 4: Approve refined results
        print("\n[Step 4/4] Approving refined results...")
        final_approved = {**refined, "hitl_approved": True}
        final = graph.invoke(final_approved, config=config)

        print(f"\n✓ Completed after refinement")
        print(f"  Final answer: {'Present' if final.get('final_answer') else 'None'}")

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Testing HITL Human-in-the-Loop Flow\n")

    test1_ok = test_hitl_approval_flow()
    test2_ok = test_hitl_rejection_flow()

    print("\n\n" + "=" * 60)
    if test1_ok and test2_ok:
        print("✅ All HITL tests passed!")
    else:
        print("❌ Some tests failed")
        sys.exit(1)
    print("=" * 60)
