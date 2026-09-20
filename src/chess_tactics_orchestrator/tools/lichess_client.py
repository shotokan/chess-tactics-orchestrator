"""
Lichess API client for fetching user games.

This tool queries the public Lichess API to retrieve games for a given username,
with filtering by opening, color, time control, and date range.

Based on official docs: https://lichess.org/api#tag/Games/operation/apiGamesUser
"""

import requests
import json
from datetime import datetime
from typing import Optional, Literal
import time
import os


class LichessClient:
    """Client for Lichess public API."""

    BASE_URL = "https://lichess.org/api"

    def __init__(self, rate_limit_delay: float = 0.5):
        """
        Initialize Lichess client.

        Args:
            rate_limit_delay: Delay in seconds between requests to respect rate limits
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()

        headers = {
            "Accept": "application/x-ndjson",
            "User-Agent": "ChessAgentOrchestrator/1.0 (contact: github.com/anonymous)"
        }

        # Add API token if available (for higher rate limits)
        api_token = os.getenv("LICHESS_API_TOKEN")
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        self.session.headers.update(headers)

    def fetch_games(
        self,
        username: str,
        max_games: Optional[int] = None,
        since: Optional[int] = None,
        until: Optional[int] = None,
        color: Optional[Literal["white", "black"]] = None,
        perf_type: Optional[str] = None,
        rated: Optional[bool] = None,
        with_analysis: bool = False,
        with_opening: bool = True,
        with_moves: bool = True,
        with_clocks: bool = False
    ) -> list[dict]:
        """
        Fetch games for a user from Lichess API.

        Args:
            username: Lichess username
            max_games: Maximum number of games to fetch
            since: Unix timestamp (ms) - fetch games played after this date
            until: Unix timestamp (ms) - fetch games played before this date
            color: Filter by color played ("white" or "black")
            perf_type: Time control filter (e.g., "blitz", "rapid", "classical")
            rated: Filter by rated games only
            with_analysis: Include server analysis if available
            with_opening: Include opening classification
            with_moves: Include game moves
            with_clocks: Include clock times

        Returns:
            List of game dictionaries from Lichess API

        Raises:
            requests.HTTPError: If API request fails
        """
        # Endpoint: GET /api/games/user/{username}
        endpoint = f"{self.BASE_URL}/games/user/{username}"

        params = {
            "moves": "true" if with_moves else "false",
            "pgnInJson": "true",  # Return moves as JSON
            "opening": "true" if with_opening else "false",
            "clocks": "true" if with_clocks else "false",
        }

        # Only add evals if requested (costs more bandwidth)
        if with_analysis:
            params["evals"] = "true"

        if max_games:
            params["max"] = max_games
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if color:
            params["color"] = color
        if perf_type:
            params["perfType"] = perf_type
        if rated is not None:
            params["rated"] = "true" if rated else "false"

        time.sleep(self.rate_limit_delay)

        response = self.session.get(endpoint, params=params, stream=True)
        response.raise_for_status()

        # Parse NDJSON (newline-delimited JSON)
        games = []
        for line in response.iter_lines():
            if line:
                try:
                    games.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

        return games

    def filter_by_opening(
        self,
        games: list[dict],
        opening_name: str,
        partial_match: bool = True
    ) -> list[dict]:
        """
        Filter games by opening name.

        Args:
            games: List of game dictionaries
            opening_name: Opening name to filter by (e.g., "Sicilian", "King's Indian")
            partial_match: If True, match if opening_name is substring of game opening

        Returns:
            Filtered list of games matching the opening
        """
        filtered = []
        opening_lower = opening_name.lower()

        for game in games:
            if "opening" not in game:
                continue

            game_opening = game["opening"].get("name", "").lower()

            if partial_match:
                if opening_lower in game_opening:
                    filtered.append(game)
            else:
                if opening_lower == game_opening:
                    filtered.append(game)

        return filtered

    @staticmethod
    def format_game_summary(game: dict) -> str:
        """
        Format a single game as a human-readable summary.

        Args:
            game: Game dictionary from Lichess API

        Returns:
            Formatted string summary
        """
        white = game["players"]["white"].get("user", {}).get("name", "Anonymous")
        black = game["players"]["black"].get("user", {}).get("name", "Anonymous")
        result = game.get("status", "unknown")
        winner = game.get("winner", "draw")

        opening = game.get("opening", {}).get("name", "Unknown opening")
        perf_type = game.get("perf", "unknown")

        timestamp = game.get("createdAt", 0)
        date = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")

        return (
            f"{date} | {white} vs {black} | {opening} | "
            f"{perf_type} | Result: {result} (winner: {winner})"
        )


# Tool function wrapper for LangChain/LangGraph integration
def fetch_lichess_games(
    username: str,
    max_games: int = 50,
    opening_filter: Optional[str] = None,
    **kwargs
) -> dict:
    """
    Tool function to fetch and optionally filter Lichess games.

    Args:
        username: Lichess username
        max_games: Maximum number of games to fetch
        opening_filter: Optional opening name to filter by
        **kwargs: Additional filters passed to LichessClient.fetch_games

    Returns:
        Dictionary with:
            - games: list of game dictionaries
            - count: number of games retrieved
            - filtered_count: number after opening filter (if applied)
    """
    client = LichessClient()
    games = client.fetch_games(username, max_games=max_games, **kwargs)

    result = {
        "games": games,
        "count": len(games),
        "filtered_count": None,
        "all_games": games  # Keep original games for debugging
    }

    if opening_filter:
        filtered_games = client.filter_by_opening(games, opening_filter)
        result["games"] = filtered_games
        result["filtered_count"] = len(filtered_games)

    return result
