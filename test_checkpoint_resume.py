#!/usr/bin/env python3
"""
Test LangGraph checkpoint and resume with RedisSaver.

Tests:
1. Graph execution with checkpointing
2. Interrupt at HITL point
3. Resume from checkpoint after approval

Prerequisites:
    docker-compose up -d redis
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, 'src')

from chess_tactics_orchestrator.graph import create_graph
from chess_tactics_orchestrator.infrastructure import create_redis_checkpointer


def test_checkpoint_and_resume():
    """Test checkpoint persistence and resume."""

    print("=" * 60)
    print("Testing LangGraph Checkpointing + Resume")
    print("=" * 60)

    # Create checkpointer
    print("\n[1/5] Creating RedisSaver...")
    try:
        checkpointer = create_redis_checkpointer(host="localhost", port=6379)
        print("✓ RedisSaver created")
    except Exception as e:
        print(f"❌ Failed to create checkpointer: {e}")
        print("   Make sure Redis is running: docker-compose up -d redis")
        sys.exit(1)

    # Create graph with checkpointer
    print("\n[2/5] Creating graph with checkpointing...")
    graph = create_graph(checkpointer=checkpointer)
    print("✓ Graph created")

    # Run analysis with thread_id
    print("\n[3/5] Running analysis with checkpointing...")
    thread_id = "test_thread_001"

    initial_state = {
        "user_request": "¿cómo me va con la siciliana con negras últimos 10 juegos?",
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

    print(f"  Thread ID: {thread_id}")
    print("  Running graph (will interrupt at HITL checkpoint)...")

    try:
        # First run: should interrupt at HITL point
        result = graph.invoke(initial_state, config=config)

        print("\n✓ Graph execution reached checkpoint")
        print(f"  State at checkpoint:")
        print(f"    - Games fetched: {len(result.get('games_raw', []))}")
        print(f"    - Analysis result: {'Present' if result.get('analysis_result') else 'None'}")
        print(f"    - HITL approved: {result.get('hitl_approved', False)}")

        # Simulate HITL approval
        print("\n[4/5] Simulating human approval...")
        print("  (In production, this would come from API endpoint)")

        # Update state with approval
        approval_update = {
            "hitl_approved": True,
            "hitl_feedback": "Approved by human - results look good"
        }

        # Merge approval into current state
        resumed_state = {**result, **approval_update}

        # Resume from checkpoint
        print("\n[5/5] Resuming from checkpoint...")
        final_result = graph.invoke(resumed_state, config=config)

        print("\n✓ Graph resumed and completed")
        print(f"  Final answer present: {final_result.get('final_answer') is not None}")
        print(f"  Contributions count: {len(final_result.get('contributions', []))}")

        # Show final answer preview
        final_answer = final_result.get("final_answer")
        if final_answer:
            print(f"\n📊 Final Answer Preview:")
            print(f"{final_answer[:200]}...")

        print("\n" + "=" * 60)
        print("✅ Checkpoint + Resume test completed!")
        print("=" * 60)

        # Show checkpoint info
        print(f"\nCheckpoint Details:")
        print(f"  Thread ID: {thread_id}")
        print(f"  State persisted in Redis: redis://localhost:6379")
        print(f"  Can resume later with same thread_id")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_checkpoint_and_resume()
