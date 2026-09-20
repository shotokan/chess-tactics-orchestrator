"""
Stockfish evaluation tool with Lichess analysis fallback.

This module evaluates chess positions using:
1. Lichess server analysis (if available in game data) - FREE
2. Local Stockfish engine (fallback for games without server eval) - SLOW

The two-tier approach minimizes computational cost while ensuring all games can be analyzed.
"""

import chess
import chess.engine
from typing import Optional, Literal
import os
from pathlib import Path


class StockfishEvaluator:
    """
    Position evaluator using Lichess analysis or Stockfish fallback.
    """

    def __init__(
        self,
        stockfish_path: Optional[str] = None,
        depth: int = 15,
        time_limit: float = 0.5
    ):
        """
        Initialize the evaluator.

        Args:
            stockfish_path: Path to Stockfish binary (uses system PATH if None)
            depth: Search depth for Stockfish analysis
            time_limit: Time limit in seconds for Stockfish analysis
        """
        self.depth = depth
        self.time_limit = time_limit
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.stockfish_path = stockfish_path or os.getenv("STOCKFISH_PATH")

    def __enter__(self):
        """Context manager entry - initialize engine if needed."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup engine."""
        self.close()

    def _ensure_engine(self):
        """Lazy-load Stockfish engine only when needed."""
        if self.engine is None:
            if self.stockfish_path:
                path = Path(self.stockfish_path)
            else:
                # Try common paths
                for candidate in ["/usr/local/bin/stockfish", "/usr/bin/stockfish", "stockfish"]:
                    path = Path(candidate)
                    if path.exists() or candidate == "stockfish":
                        break

            try:
                self.engine = chess.engine.SimpleEngine.popen_uci(str(path))
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Stockfish not found. Install it or set STOCKFISH_PATH env variable. "
                    f"Tried: {path}"
                )

    def close(self):
        """Close the Stockfish engine if it was opened."""
        if self.engine:
            self.engine.quit()
            self.engine = None

    def evaluate_position(
        self,
        board: chess.Board,
        use_lichess_eval: Optional[dict] = None
    ) -> dict:
        """
        Evaluate a position using Lichess eval (if available) or Stockfish.

        Args:
            board: Chess board position to evaluate
            use_lichess_eval: Lichess evaluation dict from game data (if available)

        Returns:
            Dictionary with:
                - score_cp: centipawn score from white's perspective (None if mate)
                - score_mate: moves to mate (None if not mate)
                - best_move: best move in UCI format (if available)
                - source: "lichess" or "stockfish"
        """
        # Try Lichess eval first
        if use_lichess_eval:
            eval_dict = use_lichess_eval.get("eval")
            if eval_dict is not None:
                # Parse Lichess eval format (can be int or dict)
                score_cp = None
                if isinstance(eval_dict, (int, float)):
                    score_cp = int(eval_dict)
                elif isinstance(eval_dict, dict):
                    score_cp = eval_dict.get("value")

                return {
                    "score_cp": score_cp,
                    "score_mate": use_lichess_eval.get("mate"),
                    "best_move": use_lichess_eval.get("best"),
                    "source": "lichess"
                }

        # Fallback to Stockfish
        self._ensure_engine()

        info = self.engine.analyse(
            board,
            chess.engine.Limit(depth=self.depth, time=self.time_limit)
        )

        score = info["score"].white()

        return {
            "score_cp": score.score() if not score.is_mate() else None,
            "score_mate": score.mate() if score.is_mate() else None,
            "best_move": info.get("pv", [None])[0].uci() if "pv" in info else None,
            "source": "stockfish"
        }

    def detect_blunder(
        self,
        before_eval: dict,
        after_eval: dict,
        side: Literal["white", "black"],
        threshold_cp: int = 75
    ) -> bool:
        """
        Detect if a move was a blunder based on evaluation swing.

        Args:
            before_eval: Evaluation before the move
            after_eval: Evaluation after the move
            side: Which side made the move
            threshold_cp: Centipawn threshold for blunder (default 75 = 0.75 pawns)

        Returns:
            True if the move was a blunder
        """
        # Handle mate scores
        if before_eval["score_mate"] is not None:
            # If side was winning (mate in N) and lost it, that's a blunder
            if side == "white" and before_eval["score_mate"] > 0:
                return after_eval["score_mate"] is None or after_eval["score_mate"] <= 0
            if side == "black" and before_eval["score_mate"] < 0:
                return after_eval["score_mate"] is None or after_eval["score_mate"] >= 0

        if after_eval["score_mate"] is not None:
            # Got mated - definitely a blunder
            if side == "white" and after_eval["score_mate"] < 0:
                return True
            if side == "black" and after_eval["score_mate"] > 0:
                return True

        # Centipawn-based blunder detection
        before_cp = before_eval.get("score_cp")
        after_cp = after_eval.get("score_cp")

        if before_cp is None or after_cp is None:
            return False

        # Calculate swing (positive = good for white)
        swing = after_cp - before_cp

        # For white, a large negative swing is bad
        # For black, a large positive swing is bad
        if side == "white":
            return swing < -threshold_cp
        else:
            return swing > threshold_cp


def analyze_game_moves(
    game: dict,
    evaluator: StockfishEvaluator,
    sample_every_n_moves: int = 1,
    debug: bool = False
) -> dict:
    """
    Analyze all moves in a game to detect blunders and evaluation swings.

    Args:
        game: Game dictionary from Lichess API
        evaluator: StockfishEvaluator instance
        sample_every_n_moves: Only analyze every Nth move to save time (1 = all moves)

    Returns:
        Dictionary with:
            - move_evals: list of evaluations for each analyzed position
            - blunders_white: list of move indices where white blundered
            - blunders_black: list of move indices where black blundered
            - lichess_eval_count: number of positions with Lichess eval
            - stockfish_eval_count: number of positions evaluated with Stockfish
    """
    if "moves" not in game or not game["moves"]:
        return {
            "move_evals": [],
            "blunders_white": [],
            "blunders_black": [],
            "lichess_eval_count": 0,
            "stockfish_eval_count": 0
        }

    board = chess.Board()
    move_list = game["moves"].split() if isinstance(game["moves"], str) else game["moves"]

    # Get Lichess analysis if available
    lichess_analysis = game.get("analysis", [])

    move_evals = []
    blunders_white = []
    blunders_black = []
    lichess_count = 0
    stockfish_count = 0

    for i, move_san in enumerate(move_list):
        if i % sample_every_n_moves != 0:
            board.push_san(move_san)
            continue

        # Get eval before move i (the current board position)
        # For move 0: no previous analysis, so use Stockfish
        # For move i > 0: lichess_analysis[i-1] has eval AFTER move i-1 which is BEFORE move i
        # BUT: lichess_analysis[i-1]["best"] is the best move from position AFTER i-1 (our current position!)
        lichess_eval_before = lichess_analysis[i - 1] if i > 0 and i - 1 < len(lichess_analysis) else None
        eval_before = evaluator.evaluate_position(board, lichess_eval_before)

        if eval_before["source"] == "lichess":
            lichess_count += 1
        else:
            stockfish_count += 1

        # Make the move
        board.push_san(move_san)

        # Get eval after move i (the position after playing move i)
        # lichess_analysis[i] has eval AFTER move i
        lichess_eval_after = lichess_analysis[i] if i < len(lichess_analysis) else None
        eval_after = evaluator.evaluate_position(board, lichess_eval_after)

        if eval_after["source"] == "lichess":
            lichess_count += 1
        else:
            stockfish_count += 1

        move_evals.append({
            "move_index": i,
            "move": move_san,
            "eval_before": eval_before,
            "eval_after": eval_after
        })

        # Detect blunders
        side = "white" if i % 2 == 0 else "black"
        is_blunder = evaluator.detect_blunder(eval_before, eval_after, side)

        if debug and i < 5:  # Debug first 5 moves only
            print(f"\n[DEBUG] Move {i} ({side}): {move_san}")
            print(f"  Before: cp={eval_before.get('score_cp')}, mate={eval_before.get('score_mate')}, src={eval_before.get('source')}")
            print(f"  After:  cp={eval_after.get('score_cp')}, mate={eval_after.get('score_mate')}, src={eval_after.get('source')}")
            print(f"  Blunder: {is_blunder}")

        if is_blunder:
            if side == "white":
                blunders_white.append(i)
            else:
                blunders_black.append(i)

    return {
        "move_evals": move_evals,
        "blunders_white": blunders_white,
        "blunders_black": blunders_black,
        "lichess_eval_count": lichess_count,
        "stockfish_eval_count": stockfish_count
    }
