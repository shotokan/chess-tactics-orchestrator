"""
Main orchestration graph for the chess tactics analyzer.

This module defines the LangGraph StateGraph that coordinates the multi-agent system.
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from chess_tactics_orchestrator.state import AgentState
from chess_tactics_orchestrator.agents.research_agent import research_node
from chess_tactics_orchestrator.agents.analyst_agent import analyst_node
from chess_tactics_orchestrator.agents.supervisor import supervisor_node, supervisor_routing


def create_graph() -> CompiledStateGraph:
    """
    Create and compile the orchestration graph.

    Graph structure:
        START → supervisor → {research, analyst, END}
                    ↑            ↓         ↓
                    └────────────┴─────────┘
                      (results loop back)

    Returns:
        Compiled StateGraph ready for invocation
    """
    # Create graph with AgentState schema
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("research", research_node)
    workflow.add_node("analyst", analyst_node)

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Add conditional edges from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_routing,  # Function that returns Literal["research", "analyst", "end"]
        {
            "research": "research",
            "analyst": "analyst",
            "end": END
        }
    )

    # Both specialists loop back to supervisor for validation/routing
    workflow.add_edge("research", "supervisor")
    workflow.add_edge("analyst", "supervisor")

    # Compile the graph
    return workflow.compile()


def run_query(user_request: str, username: str) -> dict:
    """
    Run a natural language query through the orchestrator.

    Args:
        user_request: Natural language question (e.g., "How did I do with Sicilian in the last 3 months?")
        username: Lichess username to analyze

    Returns:
        Final state with analysis results
    """
    graph = create_graph()

    # Initialize state
    initial_state = {
        "user_request": f"{user_request} (username: {username})",
        "games_raw": [],
        "contributions": [],
        "analysis_result": None,
        "analysis_metadata": {},
        "needs_refinement": False,
        "refine_target": None,
        "refinement_count": 0,
        "final_answer": None
    }

    # Run the graph
    final_state = graph.invoke(initial_state)

    return final_state
