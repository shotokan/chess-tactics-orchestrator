"""
Analyst Agent - computes metrics and interprets chess game data.

This agent analyzes the games fetched by the research agent and computes the 5 metrics:
1. Winrate by opening
2. Winrate by color
3. Game termination types
4. Winrate by endgame type
5. Tactical patterns missed (from real games, not puzzle dashboard)
"""

from typing import Optional
from datetime import datetime
from collections import Counter
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from chess_tactics_orchestrator.state import AgentState, Contribution
from chess_tactics_orchestrator.tools.stockfish_eval import (
    StockfishEvaluator,
    analyze_game_moves,
)
from chess_tactics_orchestrator.tools.tactic_detector import (
    analyze_tactics_in_game,
    EndgameClassifier,
)
import chess


class AnalystAgent:
    """
    Agent responsible for analyzing games and computing metrics.

    Computes 5 metrics and provides LLM interpretation of the results.
    """

    def __init__(self, model_name: str = "gemini-3.5-flash"):
        """
        Initialize the analyst agent.

        Args:
            model_name: Gemini model to use (default: Gemini 2.5 Flash)
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.3,  # Slight creativity for interpretation
        )

        self.system_prompt = """Eres un especialista en análisis de ajedrez.

Tu trabajo es interpretar resultados estadísticos del análisis de partidas y proporcionar insights
en lenguaje natural EN ESPAÑOL.

Recibirás métricas estructuradas sobre el rendimiento de un jugador. Tu tarea es:
1. Identificar fortalezas y debilidades
2. Señalar patrones y tendencias
3. Proporcionar insights accionables
4. Notar cualquier limitación en los datos

Sé conciso pero perspicaz. Evita consejos genéricos como "practica más" - en lugar de eso,
enfócate en lo que los datos realmente muestran.

Si los datos son insuficientes (< 10 partidas), indica claramente las limitaciones al inicio.

IMPORTANTE: Toda tu respuesta debe estar en ESPAÑOL.
"""

    def compute_metrics(
        self, games: list[dict], target_username: str, sample_moves: bool = True
    ) -> dict:
        """
        Compute all 5 metrics from the games.

        Args:
            games: List of game dictionaries from Lichess
            target_username: Username of the player being analyzed
            sample_moves: If True, only analyze every 3rd move to save time

        Returns:
            Dictionary with all computed metrics
        """
        if not games:
            return {"error": "No games to analyze", "games_analyzed": 0}

        # Metric 1: Winrate by opening
        opening_stats = Counter()
        opening_games = {}

        for game in games:
            opening = game.get("opening", {}).get("name", "Unknown")
            player_color = self._get_player_color(game, target_username)

            if player_color == "unknown":
                continue  # Skip games where player is not found

            if opening not in opening_games:
                opening_games[opening] = {"wins": 0, "total": 0}

            opening_games[opening]["total"] += 1

            winner = game.get("winner")

            if (winner == "white" and player_color == "white") or (
                winner == "black" and player_color == "black"
            ):
                opening_games[opening]["wins"] += 1

        opening_winrates = {
            opening: {
                "winrate": stats["wins"] / stats["total"] if stats["total"] > 0 else 0,
                "games": stats["total"],
            }
            for opening, stats in opening_games.items()
        }

        # Metric 2: Winrate by color
        color_stats = {
            "white": {"wins": 0, "total": 0},
            "black": {"wins": 0, "total": 0},
        }

        for game in games:
            player_color = self._get_player_color(game, target_username)
            if player_color == "unknown":
                continue  # Skip games where player is not found

            winner = game.get("winner")

            color_stats[player_color]["total"] += 1

            if winner == player_color:
                color_stats[player_color]["wins"] += 1

        color_winrates = {
            color: {
                "winrate": stats["wins"] / stats["total"] if stats["total"] > 0 else 0,
                "games": stats["total"],
            }
            for color, stats in color_stats.items()
        }

        # Metric 3: Game termination types
        termination_stats = Counter()

        for game in games:
            status = game.get("status", "unknown")
            termination_stats[status] += 1

        # Metric 4 & 5: Endgame types and tactical patterns (requires move analysis)
        endgame_stats = {}
        tactical_patterns = {"white": Counter(), "black": Counter()}
        total_blunders = {"white": 0, "black": 0}

        lichess_eval_count = 0
        stockfish_eval_count = 0

        # Only analyze games with moves
        games_to_analyze = [g for g in games if "moves" in g and g["moves"]]
        sample_every = 3 if sample_moves else 1

        print(
            f"  📊 Analizando {min(len(games_to_analyze), 20)} partidas para detectar blunders..."
        )

        with StockfishEvaluator() as evaluator:
            for idx, game in enumerate(
                games_to_analyze[:20], 1
            ):  # Limit to 20 games for performance
                print(f"    [{idx}/20] Evaluando partida...", end="\r")
                # Analyze moves for blunders
                move_analysis = analyze_game_moves(
                    game, evaluator, sample_every_n_moves=sample_every, debug=(idx == 1)
                )

                lichess_eval_count += move_analysis["lichess_eval_count"]
                stockfish_eval_count += move_analysis["stockfish_eval_count"]

                # Analyze tactics
                tactics = analyze_tactics_in_game(
                    game,
                    move_analysis["move_evals"],
                    move_analysis["blunders_white"],
                    move_analysis["blunders_black"],
                )

                # Accumulate tactical patterns
                player_color = self._get_player_color(game, target_username)

                if player_color == "unknown":
                    continue  # Skip tactical analysis if player not found

                for pattern, count in tactics[f"patterns_{player_color}"].items():
                    tactical_patterns[player_color][pattern] += count

                total_blunders[player_color] += tactics[
                    f"total_blunders_{player_color}"
                ]

                # Track endgame type with result
                endgame_type = tactics["endgame_type"]
                if endgame_type:
                    if endgame_type not in endgame_stats:
                        endgame_stats[endgame_type] = {"wins": 0, "total": 0}

                    endgame_stats[endgame_type]["total"] += 1

                    winner = game.get("winner")
                    if winner == player_color:
                        endgame_stats[endgame_type]["wins"] += 1

        print(f"\n  ✓ Análisis táctico completado")
        print(f"    - Blunders detectados: {total_blunders}")
        print(
            f"    - Fuentes de evaluación: Lichess={lichess_eval_count}, Stockfish={stockfish_eval_count}"
        )

        endgame_winrates = {
            eg_type: {
                "winrate": stats["wins"] / stats["total"] if stats["total"] > 0 else 0,
                "games": stats["total"],
            }
            for eg_type, stats in endgame_stats.items()
        }

        return {
            "games_analyzed": len(games),
            "opening_winrates": opening_winrates,
            "color_winrates": color_winrates,
            "termination_types": dict(termination_stats),
            "endgame_winrates": endgame_winrates,
            "tactical_patterns": {
                color: dict(patterns) for color, patterns in tactical_patterns.items()
            },
            "total_blunders": total_blunders,
            "eval_sources": {
                "lichess": lichess_eval_count,
                "stockfish": stockfish_eval_count,
            },
        }

    def _get_player_color(self, game: dict, username: str) -> str:
        """Determine which color the target player had in this game."""
        white_user = (
            game.get("players", {})
            .get("white", {})
            .get("user", {})
            .get("name", "")
            .lower()
        )
        black_user = (
            game.get("players", {})
            .get("black", {})
            .get("user", {})
            .get("name", "")
            .lower()
        )

        if white_user == username.lower():
            return "white"
        elif black_user == username.lower():
            return "black"
        else:
            return "unknown"

    def interpret_metrics(self, metrics: dict, user_request: str) -> str:
        """
        Use LLM to interpret metrics and generate natural language insights.

        Args:
            metrics: Computed metrics dictionary
            user_request: Original user request

        Returns:
            Natural language interpretation
        """
        # Determine which color the user played
        color_stats = metrics["color_winrates"]
        user_color = "black" if color_stats["black"]["games"] > 0 else "white"
        user_games = color_stats[user_color]["games"]
        user_winrate = color_stats[user_color]["winrate"]

        metrics_text = f"""
User question: {user_request}

CRITICAL CONTEXT - READ THIS FIRST:
The user asked about playing as {user_color}. ALL {user_games} games in this analysis are games where the user played as {user_color}.

If you see "white: games=0" or "black: games=0", this is CORRECT because:
- The games were filtered by color (the user only played as {user_color} in these games)
- This is NOT a data error or limitation
- Do NOT say there are "0 games with {user_color}" - there are {user_games} games where the user played as {user_color}

Analysis results for {user_games} games playing as {user_color}:
- Overall winrate: {user_winrate:.1%}

Winrate by opening (specific variations):
{self._format_dict(metrics["opening_winrates"])}

Game termination types:
{metrics["termination_types"]}

Endgame performance:
{self._format_dict(metrics["endgame_winrates"])}

Tactical patterns (blunders by the user playing as {user_color}):
{metrics["tactical_patterns"][user_color]}
Total blunders by user: {metrics["total_blunders"][user_color]}

Evaluation sources:
- Lichess server analysis: {metrics["eval_sources"]["lichess"]} positions
- Stockfish local eval: {metrics["eval_sources"]["stockfish"]} positions
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=metrics_text),
        ]

        response = self.llm.invoke(messages)

        # Handle both string and list responses from Gemini
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)

        return content

    def _format_dict(self, d: dict) -> str:
        """Format a dict for text display."""
        return "\n".join(f"  {k}: {v}" for k, v in d.items())

    def run(self, state: AgentState) -> dict:
        """
        Execute the analyst agent.

        Args:
            state: Current agent state

        Returns:
            Updated state with analysis_result and final_answer
        """
        games = state["games_raw"]
        user_request = state["user_request"]

        # Extract username: check both colors in first and last game to find the common player
        username = "unknown"
        if games:
            first_game = games[0]
            white_name = (
                first_game.get("players", {})
                .get("white", {})
                .get("user", {})
                .get("name")
            )
            black_name = (
                first_game.get("players", {})
                .get("black", {})
                .get("user", {})
                .get("name")
            )

            if len(games) > 1:
                # Check which player appears in both first and last game
                last_game = games[-1]
                last_white = (
                    last_game.get("players", {})
                    .get("white", {})
                    .get("user", {})
                    .get("name")
                )
                last_black = (
                    last_game.get("players", {})
                    .get("black", {})
                    .get("user", {})
                    .get("name")
                )

                # The target user appears in both games
                if white_name and (
                    white_name == last_white or white_name == last_black
                ):
                    username = white_name
                elif black_name and (
                    black_name == last_white or black_name == last_black
                ):
                    username = black_name
                else:
                    username = white_name or black_name or "unknown"
            else:
                # Single game: guess based on order (white first, then black)
                username = white_name or black_name or "unknown"

        # Compute metrics
        metrics = self.compute_metrics(games, username, sample_moves=True)

        # Check for gaps
        gaps = []
        answers_question = True

        if metrics.get("games_analyzed", 0) < 10:
            gaps.append(
                f"Only {metrics.get('games_analyzed', 0)} games analyzed (ideal: 10+)"
            )
            answers_question = False

        if metrics.get("error"):
            gaps.append(metrics["error"])
            answers_question = False

        # Interpret with LLM
        interpretation = self.interpret_metrics(metrics, user_request)

        return {
            "analysis_result": {
                "metrics": metrics,
                "interpretation": interpretation,
                "answers_user_question": answers_question,
                "gaps": gaps,
            },
            "analysis_metadata": metrics.get("eval_sources", {}),
            "contributions": [
                Contribution(
                    agent="analyst",
                    summary=f"Analyzed {metrics.get('games_analyzed', 0)} games, computed 5 metrics",
                    timestamp=datetime.now().isoformat(),
                )
            ],
            "final_answer": interpretation if answers_question else None,
            "needs_refinement": not answers_question,
        }


# Node function for LangGraph integration
def analyst_node(state: AgentState) -> dict:
    """
    LangGraph node wrapper for the analyst agent.

    Args:
        state: Current state

    Returns:
        State updates
    """
    agent = AnalystAgent()
    return agent.run(state)
