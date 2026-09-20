"""
Supervisor Agent - dynamic routing and validation.

This agent has two responsibilities:
1. Routing: decide which specialist to invoke next (research, analyst, or end)
2. Validation: apply a rubric to results before allowing END
"""

from typing import Literal, cast
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from chess_tactics_orchestrator.state import AgentState


class SupervisorAgent:
    """
    Supervisor that routes between specialist agents and validates results.
    """

    # Hard limits to prevent infinite loops
    MAX_REFINEMENT_CYCLES = 2
    MIN_GAMES_REQUIRED = 10

    def __init__(self, model_name: str = "gemini-3.6-flash"):
        """
        Initialize the supervisor.

        Args:
            model_name: Gemini model to use (default: Gemini 3.6 Flash)
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)

        self.routing_prompt = """You are a supervisor coordinating specialist agents for chess analysis.

You must decide which specialist to invoke next based on the current state:

Available specialists:
- "research": Fetches games from Lichess based on user request
- "analyst": Analyzes games and computes metrics
- "end": Finish and return results to user

Routing logic:
1. If games_raw is empty → route to "research"
2. If games_raw exists but analysis_result is None → route to "analyst"
3. If needs_refinement is True → route to the agent specified in refine_target
4. If analysis_result exists and answers_user_question is True → route to "end"
5. If refinement_count >= 2 → route to "end" (hard limit reached)

You MUST respond with ONLY one word: "research", "analyst", or "end"
No explanations, no punctuation, just the single word.
"""

        self.validation_prompt = """You are validating chess analysis results against quality criteria.

Evaluation rubric:
1. Completeness: Are there >= 10 games analyzed?
2. Relevance: Do the games match what the user asked for?
3. Depth: Does the analysis go beyond simple aggregates?
4. Gaps: Did the agent report any critical limitations?

Based on the analysis result, determine:
- Is it complete enough to answer the user's question?
- If not, which agent should be refined (research or analyst)?
- What specific improvements are needed?

Respond in this exact format:
COMPLETE: yes/no
REASON: <one sentence explanation>
REFINE_TARGET: research/analyst/none
INSTRUCTIONS: <what needs improvement>
"""

    def route(
        self, state: AgentState
    ) -> Literal["research", "analyst", "hitl_approval", "end"]:
        """
        Determine which node to invoke next.

        Args:
            state: Current agent state

        Returns:
            Next node to invoke (including "hitl_approval" for HITL)
        """
        # HITL checkpoint: if analyst has result but not yet approved, go to HITL node
        analysis_result = state.get("analysis_result")
        if analysis_result is not None and not state.get("hitl_approved", False):
            # Route to HITL approval node (graph will interrupt before executing it)
            return "hitl_approval"

        # Hard deterministic checks first (no LLM needed)

        # Check refinement limit
        if state.get("refinement_count", 0) >= self.MAX_REFINEMENT_CYCLES:
            return "end"

        # Check if we need to refine
        if state.get("needs_refinement") and state.get("refine_target"):
            return state["refine_target"]

        # Check if we have games
        if not state.get("games_raw"):
            return "research"

        # Check if we have analysis
        if analysis_result is None:
            return "analyst"

        # Check if analysis answers the question and has been approved
        if analysis_result.get("answers_user_question") and state.get("hitl_approved"):
            return "end"

        # Fallback to LLM-based routing if deterministic rules don't apply
        state_summary = self._summarize_state(state)

        messages = [
            SystemMessage(content=self.routing_prompt),
            HumanMessage(content=state_summary),
        ]

        response = self.llm.invoke(messages)

        # Handle both string and list responses from Gemini
        content = response.content
        if isinstance(content, list):
            # Gemini sometimes returns list of content blocks
            content = " ".join(str(item) for item in content)

        decision = content.strip().lower()

        # Validate response
        if decision not in ["research", "analyst", "end"]:
            # Default to end if LLM gives invalid response
            return "end"

        return cast(Literal["research", "analyst", "hitl_approval", "end"], decision)

    def validate(self, state: AgentState) -> dict:
        """
        Validate results before allowing END.

        Args:
            state: Current agent state

        Returns:
            Dictionary with validation results and refinement instructions
        """
        # Deterministic checks first
        games_count = len(state.get("games_raw", []))

        if games_count < self.MIN_GAMES_REQUIRED:
            return {
                "complete": False,
                "reason": f"Only {games_count} games, need {self.MIN_GAMES_REQUIRED}+",
                "refine_target": "research",
                "instructions": "Fetch more games with broader filters",
            }

        analysis_result = state.get("analysis_result")

        if not analysis_result:
            return {
                "complete": False,
                "reason": "No analysis result present",
                "refine_target": "analyst",
                "instructions": "Complete the analysis",
            }

        # Check gaps reported by analyst
        gaps = analysis_result.get("gaps", [])
        if gaps:
            return {
                "complete": False,
                "reason": f"Gaps reported: {', '.join(gaps)}",
                "refine_target": "analyst"
                if games_count >= self.MIN_GAMES_REQUIRED
                else "research",
                "instructions": "Address reported gaps",
            }

        # LLM-based validation for deeper checks
        validation_input = f"""
User request: {state["user_request"]}

Games fetched: {games_count}

Analysis result:
{analysis_result.get("interpretation", "No interpretation")}

Gaps reported: {gaps if gaps else "None"}

Agent contributions:
{self._format_contributions(state.get("contributions", []))}
"""

        messages = [
            SystemMessage(content=self.validation_prompt),
            HumanMessage(content=validation_input),
        ]

        response = self.llm.invoke(messages)

        # Handle both string and list responses from Gemini
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)

        parsed = self._parse_validation_response(content)

        return parsed

    def _summarize_state(self, state: AgentState) -> str:
        """Create a text summary of current state for LLM routing."""
        return f"""
Current state:
- User request: {state.get("user_request", "Unknown")}
- Games fetched: {len(state.get("games_raw", []))}
- Analysis complete: {state.get("analysis_result") is not None}
- Needs refinement: {state.get("needs_refinement", False)}
- Refine target: {state.get("refine_target", "None")}
- Refinement count: {state.get("refinement_count", 0)}
- Analysis answers question: {state.get("analysis_result", {}).get("answers_user_question", False)}
"""

    def _format_contributions(self, contributions: list) -> str:
        """Format contributions list as text."""
        if not contributions:
            return "None"
        return "\n".join(f"- {c['agent']}: {c['summary']}" for c in contributions)

    def _parse_validation_response(self, response: str) -> dict:
        """Parse the structured validation response from LLM."""
        lines = response.strip().split("\n")
        result = {
            "complete": True,
            "reason": "",
            "refine_target": None,
            "instructions": "",
        }

        for line in lines:
            if line.startswith("COMPLETE:"):
                result["complete"] = "yes" in line.lower()
            elif line.startswith("REASON:"):
                result["reason"] = line.split(":", 1)[1].strip()
            elif line.startswith("REFINE_TARGET:"):
                target = line.split(":", 1)[1].strip().lower()
                if target in ["research", "analyst"]:
                    result["refine_target"] = target
            elif line.startswith("INSTRUCTIONS:"):
                result["instructions"] = line.split(":", 1)[1].strip()

        return result


def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor node for validation.

    This is called BEFORE routing to check if refinement is needed.

    Args:
        state: Current state

    Returns:
        State updates with validation results
    """
    supervisor = SupervisorAgent()

    # Only validate if we have results to validate
    if state.get("analysis_result") is not None:
        validation = supervisor.validate(state)

        if not validation["complete"]:
            return {
                "needs_refinement": True,
                "refine_target": validation["refine_target"],
                "refinement_count": state.get("refinement_count", 0) + 1,
            }

    return {"needs_refinement": False, "refine_target": None}


def supervisor_routing(
    state: AgentState,
) -> Literal["research", "analyst", "hitl_approval", "end"]:
    """
    Supervisor routing function for conditional edges.

    This is the function passed to add_conditional_edges with a Literal return type.

    Args:
        state: Current state

    Returns:
        Next node name
    """
    supervisor = SupervisorAgent()
    return supervisor.route(state)
