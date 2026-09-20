"""
CLI entry point for the chess tactics orchestrator.
"""

import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

from chess_tactics_orchestrator.graph import run_query


def cli():
    """Command-line interface for the orchestrator."""
    # Load .env file if it exists
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    parser = argparse.ArgumentParser(
        description="Chess tactics orchestrator - Analyze your Lichess games with AI"
    )
    parser.add_argument(
        "username",
        help="Lichess username to analyze"
    )
    parser.add_argument(
        "question",
        nargs="+",
        help='Question to ask (e.g., "How did I do with the Sicilian in the last 3 months?")'''
)
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed execution trace"
    )

    args = parser.parse_args()

    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable not set")
        print("Create a .env file with your Gemini API key:")
        print("  GEMINI_API_KEY=your_key_here")
        return 1

    # Join question words
    question = " ".join(args.question)

    print(f"\n{'='*60}")
    print(f"Chess Tactics Orchestrator")
    print(f"{'='*60}")
    print(f"Username: {args.username}")
    print(f"Question: {question}")
    print(f"{'='*60}\n")

    # Run the query
    try:
        print("🔍 Iniciando análisis...\n")
        result = run_query(question, args.username)

        print("\n--- Ejecución ---")
        for contribution in result.get("contributions", []):
            print(f"✓ [{contribution['agent']}] {contribution['summary']}")
        print()

        # Print final answer
        final_answer = result.get("final_answer")
        analysis_result = result.get("analysis_result", {})

        if final_answer:
            print("=== Analysis ===")
            print(final_answer)
        elif analysis_result:
            print("=== Analysis (partial) ===")
            print(analysis_result.get("interpretation", "No interpretation available"))

            gaps = analysis_result.get("gaps", [])
            if gaps:
                print("\nLimitations:")
                for gap in gaps:
                    print(f"  - {gap}")
        else:
            print("No analysis generated.")

        print()

        # Print metadata
        if args.verbose:
            print("\n--- Metadata ---")
            print(f"Games analyzed: {analysis_result.get('metrics', {}).get('games_analyzed', 0)}")
            print(f"Eval sources: {result.get('analysis_metadata', {})}")
            print(f"Refinement cycles: {result.get('refinement_count', 0)}")
            print()

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(cli())
