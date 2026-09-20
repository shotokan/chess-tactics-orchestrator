"""
Main orchestration graph for the chess tactics analyzer.

This module defines the LangGraph StateGraph that coordinates the multi-agent system.
"""

from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from chess_tactics_orchestrator.state import AgentState
from chess_tactics_orchestrator.agents.research_agent import research_node
from chess_tactics_orchestrator.agents.analyst_agent import analyst_node
from chess_tactics_orchestrator.agents.supervisor import supervisor_node, supervisor_routing
from chess_tactics_orchestrator.agents.hitl_node import hitl_approval_node


def create_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
    """
    Create and compile the orchestration graph.

    Graph structure:
        START → supervisor → {research, analyst, hitl_approval, END}
                    ↑            ↓         ↓         ↓
                    └────────────┴─────────┴─────────┘
                      (results loop back)

    Args:
        checkpointer: Optional checkpoint saver for persistence (e.g., RedisSaver)

    Returns:
        Compiled StateGraph ready for invocation
    """
    # Create graph with AgentState schema
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("research", research_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("hitl_approval", hitl_approval_node)

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Add conditional edges from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_routing,  # Function that returns Literal["research", "analyst", "hitl_approval", "end"]
        {
            "research": "research",
            "analyst": "analyst",
            "hitl_approval": "hitl_approval",
            "end": END
        }
    )

    # All nodes loop back to supervisor for validation/routing
    workflow.add_edge("research", "supervisor")
    workflow.add_edge("analyst", "supervisor")
    workflow.add_edge("hitl_approval", "supervisor")

    # Compile with optional checkpointer and interrupt before HITL
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_approval"]  # Graph pauses before this node
    )


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
