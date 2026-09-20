"""
Generate mermaid diagram of the orchestration graph.
"""

from chess_tactics_orchestrator.graph import create_graph
from pathlib import Path


def main():
    """Generate and save the graph diagram."""
    graph = create_graph()

    # Generate mermaid PNG
    output_path = Path(__file__).parent / "assets" / "graph.png"
    output_path.parent.mkdir(exist_ok=True)

    try:
        png_data = graph.get_graph().draw_mermaid_png()

        with open(output_path, "wb") as f:
            f.write(png_data)

        print(f"✓ Graph diagram saved to {output_path}")

        # Also print mermaid syntax
        mermaid_syntax = graph.get_graph().draw_mermaid()
        print("\nMermaid syntax:")
        print(mermaid_syntax)

    except Exception as e:
        print(f"✗ Failed to generate diagram: {e}")
        print("\nMermaid syntax (fallback):")
        print(graph.get_graph().draw_mermaid())


if __name__ == "__main__":
    main()
