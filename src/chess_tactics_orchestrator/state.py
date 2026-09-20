"""
AgentState schema for the chess tactics orchestrator.

This module defines the shared state passed between all nodes in the LangGraph StateGraph.
Uses Annotated with operator.add for contributions to enable append-only behavior across nodes.
"""

from typing import TypedDict, Literal, Optional, Annotated
import operator


class Contribution(TypedDict):
    """
    Record of a single agent's contribution to the analysis.

    Attributes:
        agent: Name of the agent that produced this contribution
        summary: Human-readable summary of what the agent contributed
        timestamp: ISO 8601 timestamp when the contribution was made
    """
    agent: str
    summary: str
    timestamp: str


class AgentState(TypedDict):
    """
    Shared state for the multi-agent orchestrator.

    The contributions field uses Annotated with operator.add as reducer to ensure
    each node appends to the list instead of overwriting it.

    Attributes:
        user_request: Original natural language request from the user
        games_raw: List of raw game data from Lichess API
        contributions: Append-only log of agent contributions
        analysis_result: Structured output from the analyst agent
        analysis_metadata: Metadata about the analysis (e.g., eval source counts)
        needs_refinement: Whether the supervisor flagged results for refinement
        refine_target: Which agent should be re-invoked for refinement
        refinement_count: Number of refinement cycles executed (hard limit to prevent loops)
        final_answer: Natural language answer to the user's question
    """
    user_request: str
    games_raw: list[dict]
    contributions: Annotated[list[Contribution], operator.add]
    analysis_result: Optional[dict]
    analysis_metadata: dict
    needs_refinement: bool
    refine_target: Optional[Literal["research", "analyst"]]
    refinement_count: int
    final_answer: Optional[str]
