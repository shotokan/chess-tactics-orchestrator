"""
Research Agent - fetches games from Lichess based on natural language requests.

This agent uses an LLM to parse the user's request and determine appropriate
search parameters, then invokes the Lichess API tool to retrieve matching games.
"""

from typing import Optional
from datetime import datetime, timedelta
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool

from chess_tactics_orchestrator.state import AgentState, Contribution
from chess_tactics_orchestrator.tools.lichess_client import fetch_lichess_games


@tool
def search_lichess_games(
    username: str,
    max_games: int = 200,
    opening_filter: Optional[str] = None,
    since_days_ago: Optional[int] = None,
    color: Optional[str] = None,
    perf_type: Optional[str] = None,
) -> dict:
    """
    Search for games on Lichess with flexible filters.

    Args:
        username: Lichess username to fetch games for
        max_games: Maximum number of games to retrieve (default 200)
        opening_filter: Filter by opening name (e.g., "Sicilian", "King's Indian")
        since_days_ago: Only games from last N days (e.g., 90 for 3 months)
        color: Filter by color played ("white" or "black")
        perf_type: Time control (e.g., "blitz", "rapid", "classical", "bullet")

    Returns:
        Dictionary with games list and metadata
    """
    kwargs = {}

    if color:
        kwargs["color"] = color

    if perf_type:
        kwargs["perf_type"] = perf_type

    if since_days_ago:
        since_date = datetime.now() - timedelta(days=since_days_ago)
        kwargs["since"] = int(since_date.timestamp() * 1000)

    return fetch_lichess_games(
        username=username,
        max_games=max_games,
        opening_filter=opening_filter,
        with_analysis=True,  # Request server analysis for blunder detection
        **kwargs,
    )


class ResearchAgent:
    """
    Agent responsible for fetching games from Lichess based on user requests.

    Uses an LLM to interpret natural language queries and map them to API parameters.
    """

    def __init__(self, model_name: str = "gemini-3.5-flash"):
        """
        Initialize the research agent.

        Args:
            model_name: Gemini model to use (default: Gemini 2.5 Flash)
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,  # Deterministic for parameter extraction
        ).bind_tools([search_lichess_games])

        self.system_prompt = """You are a chess trainer, and specialist for chess game analysis.

Your job is to interpret the user's natural language request and fetch the appropriate
games from Lichess using the search_lichess_games tool.

Key responsibilities:
1. Extract search parameters from the user's request (opening, color, time control, date range)
2. Call the search_lichess_games tool with appropriate parameters
3. Report what you found and any limitations

Parameter mapping guidelines:
- Time ranges: "last 3 months" / "últimos 3 meses" → since_days_ago=90, "last month" → since_days_ago=30, etc.
- Opening names: Extract the opening name mentioned (e.g., "Sicilian"/"Siciliana" → "Sicilian", "Ruy Lopez" → "Ruy Lopez", "French"/"Francesa" → "French", etc.)
  - Use the ENGLISH name for the opening in opening_filter parameter
  - The filter will match partial names (e.g., "Sicilian" matches "Sicilian Defense: Dragon Variation")
- Color filters (IMPORTANT - pay attention to Spanish and English phrases):
  - "as white" / "con blancas" / "con las blancas" / "jugando blancas" / "jugando con blancas" → color="white"
  - "as black" / "con negras" / "con las negras" / "jugando negras" / "jugando con negras" → color="black"
  - If the user says "con las negras" or "con negras" or "jugando negras", they are EXPLICITLY asking for black pieces → set color="black"
  - If the user says "con las blancas" or "con blancas" or "jugando blancas", they are EXPLICITLY asking for white pieces → set color="white"
- Time controls: "blitz" / "rápidas" → perf_type="blitz", "rapid" → perf_type="rapid", "bullet" → perf_type="bullet", "classical" / "clásicas" → perf_type="classical"

CRITICAL: Only skip the color parameter if the user does NOT mention any color at all.
Examples:
- "cómo me va con la siciliana con las negras?" → opening_filter="Sicilian", color="black" ✓
- "how did I do with the Sicilian as black?" → opening_filter="Sicilian", color="black" ✓
- "cómo me va con la siciliana?" (no color mentioned) → opening_filter="Sicilian", NO color filter ✓

If the username is not specified in the request, you MUST ask for it - you cannot proceed
without a username.

After fetching games, report:
- How many games were found
- Whether filters were applied and how many matched
- Any limitations (e.g., "only 12 games found, less than the ideal minimum of 20")
"""

    def run(self, state: AgentState) -> dict:
        """
        Execute the research agent.

        Args:
            state: Current agent state

        Returns:
            Updated state with games_raw populated and a contribution logged
        """
        user_request = state["user_request"]

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"User request: {user_request}"),
        ]

        # Invoke LLM with tool binding
        response = self.llm.invoke(messages)

        # Check if LLM called the tool
        if not response.tool_calls:
            # LLM didn't call tool - likely needs clarification
            return {
                "contributions": [
                    Contribution(
                        agent="research",
                        summary=f"Cannot proceed: {response.content}",
                        timestamp=datetime.now().isoformat(),
                    )
                ],
                "games_raw": [],
                "needs_refinement": True,
                "refine_target": "research",
            }

        # Execute the tool call
        tool_call = response.tool_calls[0]

        # Debug: log the parameters being sent
        print(f"\n  🔍 Parámetros de búsqueda:")
        for key, value in tool_call["args"].items():
            print(f"    - {key}: {value}")

        tool_result = search_lichess_games.invoke(tool_call["args"])

        games = tool_result["games"]
        count = tool_result["count"]
        filtered_count = tool_result.get("filtered_count")

        # Debug: show what openings were found BEFORE filtering
        if "opening_filter" in tool_call["args"] and count > 0:
            print(
                f"\n  📋 Aperturas encontradas en las {count} partidas ANTES del filtro:"
            )
            openings = {}
            for game in tool_result.get("all_games", games):
                opening_name = game.get("opening", {}).get("name", "Unknown")
                openings[opening_name] = openings.get(opening_name, 0) + 1

            for opening, count_games in sorted(
                openings.items(), key=lambda x: x[1], reverse=True
            )[:10]:
                print(f"    - {opening}: {count_games} partidas")

            if filtered_count == 0:
                print(
                    f"\n  ⚠️  Filtro '{tool_call['args']['opening_filter']}' resultó en 0 partidas"
                )

        # Build summary
        if filtered_count is not None:
            summary = f"Fetched {count} games, {filtered_count} matched filters"
        else:
            summary = f"Fetched {count} games"

        # Check if we have enough games
        needs_refinement = False
        if len(games) < 10:
            summary += f" (WARNING: only {len(games)} games, ideally need 10+)"
            needs_refinement = True

        return {
            "games_raw": games,
            "contributions": [
                Contribution(
                    agent="research",
                    summary=summary,
                    timestamp=datetime.now().isoformat(),
                )
            ],
            "needs_refinement": needs_refinement,
            "refine_target": "research" if needs_refinement else None,
        }


# Node function for LangGraph integration
def research_node(state: AgentState) -> dict:
    """
    LangGraph node wrapper for the research agent.

    Args:
        state: Current state

    Returns:
        State updates
    """
    agent = ResearchAgent()
    return agent.run(state)
