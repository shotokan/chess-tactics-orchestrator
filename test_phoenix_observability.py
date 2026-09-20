#!/usr/bin/env python3
"""
Test Phoenix observability with a simple end-to-end analysis.

Prerequisites:
    docker-compose up -d

Usage:
    export PATH="$HOME/.local/bin:$PATH"
    uv run test_phoenix_observability.py
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Setup Phoenix BEFORE importing any LangChain/LangGraph code
from chess_tactics_orchestrator.observability import setup_observability

setup_observability()

# Now import the rest
sys.path.insert(0, 'src')

from chess_tactics_orchestrator.graph import create_graph


def test_phoenix_with_real_analysis():
    """Test Phoenix tracing with a real analysis workflow."""

    print("=" * 60)
    print("Testing Phoenix Observability - End-to-End Analysis")
    print("=" * 60)

    # Create graph
    print("\n[1/3] Creating LangGraph...")
    graph = create_graph()
    print("✓ Graph created")

    # Run analysis
    print("\n[2/3] Running analysis (with Phoenix tracing)...")
    user_request = "¿cómo me va con la siciliana con negras últimos 20 juegos?"

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
    }

    print(f"  Query: {user_request}")
    print("  Running graph...")

    try:
        result = graph.invoke(initial_state)

        print("\n✓ Analysis completed")
        print(f"  Games analyzed: {result.get('analysis_result', {}).get('metrics', {}).get('games_analyzed', 0)}")
        print(f"  Contributions: {len(result.get('contributions', []))}")

        # Show final answer
        final_answer = result.get("final_answer")
        if final_answer:
            print(f"\n📊 Final Answer:\n{final_answer[:300]}...")
        else:
            print("\n⚠️  No final answer generated")

    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Instructions for viewing traces
    print("\n[3/3] Viewing traces in Phoenix...")
    print("=" * 60)
    print("✅ Test completed successfully!")
    print("\nTo view traces in Phoenix UI:")
    print("  1. Open browser: http://localhost:6006")
    print("  2. Navigate to 'Traces' tab")
    print("  3. Find project: 'chess-tactics-orchestrator'")
    print("  4. Inspect spans:")
    print("     - research_agent (Lichess API calls)")
    print("     - analyst_agent > compute_metrics (Stockfish analysis)")
    print("     - analyst_agent > interpret_metrics (LLM interpretation)")
    print("=" * 60)


if __name__ == "__main__":
    test_phoenix_with_real_analysis()
