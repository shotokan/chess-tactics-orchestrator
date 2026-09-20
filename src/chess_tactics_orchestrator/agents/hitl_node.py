"""
Human-in-the-Loop (HITL) approval node.

This node pauses execution and waits for human approval before proceeding.
When used with checkpointing, the graph state persists in Redis and can be
resumed after approval/rejection via API.
"""

from chess_tactics_orchestrator.state import AgentState, Contribution
from datetime import datetime


def hitl_approval_node(state: AgentState) -> dict:
    """
    HITL checkpoint node - pauses for human approval.

    This node is a NO-OP placeholder. The actual interruption happens via
    the supervisor's routing logic returning "__interrupt__".

    When the graph is compiled with interrupt_before=["hitl_approval"],
    execution stops here and waits for:
    1. Human to review analysis results
    2. Human to approve/reject via API
    3. Graph.invoke() called again with updated state

    Args:
        state: Current agent state (should have analysis_result populated)

    Returns:
        Empty dict (node doesn't modify state, just acts as checkpoint)

    Usage in API:
        # Initial run - stops at HITL
        result = graph.invoke(state, config={"configurable": {"thread_id": job_id}})

        # After approval
        approved_state = {**result, "hitl_approved": True}
        final = graph.invoke(approved_state, config={"configurable": {"thread_id": job_id}})

        # After rejection with feedback
        rejected_state = {
            **result,
            "hitl_approved": False,
            "hitl_feedback": "Need more games",
            "needs_refinement": True,
            "refine_target": "research"
        }
        refined = graph.invoke(rejected_state, config={"configurable": {"thread_id": job_id}})
    """
    # Add contribution to track HITL checkpoint
    contribution = Contribution(
        agent="hitl",
        summary="Waiting for human approval",
        timestamp=datetime.now().isoformat(),
    )

    return {
        "contributions": [contribution]
    }


# Alias for backward compatibility
approval_node = hitl_approval_node
