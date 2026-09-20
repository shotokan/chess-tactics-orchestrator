"""
Tactic pattern detector and endgame classifier.

This module provides:
1. Geometric heuristic-based detection of missed tactical patterns (hanging pieces, forks, missed mates)
2. Endgame type classification based on material
"""

import chess
from typing import Literal, Optional
from collections import Counter


class TacticDetector:
    """
    Detects missed tactical patterns using geometric heuristics.

    Limited to 3 reliably detectable patterns without ML:
    - Hanging pieces (undefended pieces that could be captured)
    - Forks/double attacks (one piece attacking 2+ valuable targets)
    - Missed mates (Stockfish says mate in N, player didn't play it)
    """

    PIECE_VALUES = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0  # King can't be "won"
    }

    def classify_blunder_pattern(
        self,
        board: chess.Board,
        player_move: chess.Move,
        best_move: chess.Move,
        eval_before: dict,
        eval_after: dict
    ) -> Optional[Literal["hanging_piece", "fork", "missed_mate"]]:
        """
        Classify what tactical pattern was missed in a blunder.

        Args:
            board: Board position BEFORE the blunder
            player_move: The move the player actually made
            best_move: The best move according to engine
            eval_before: Evaluation before the move
            eval_after: Evaluation after the move

        Returns:
            Pattern type if detected, None if unclassified
        """
        # Check for missed mate first
        if self._is_missed_mate(eval_before, eval_after):
            return "missed_mate"

        # Make the best move on a copy to analyze what was missed
        board_copy = board.copy()
        board_copy.push(best_move)

        # Check for fork
        if self._is_fork(board_copy, best_move):
            return "fork"

        # Check for hanging piece capture
        if self._is_hanging_piece_capture(board_copy, best_move):
            return "hanging_piece"

        return None

    def _is_missed_mate(self, eval_before: dict, eval_after: dict) -> bool:
        """Check if player missed a forced mate."""
        mate_before = eval_before.get("score_mate")
        mate_after = eval_after.get("score_mate")

        if mate_before is None:
            return False

        # Player had mate in N and didn't play it
        # (eval_after either has no mate or worse mate)
        if mate_after is None:
            return True

        # Mate got longer = missed the faster mate
        return abs(mate_after) > abs(mate_before)

    def _is_fork(self, board: chess.Board, move: chess.Move) -> bool:
        """
        Check if a move creates a fork (attacks 2+ valuable pieces simultaneously).

        Args:
            board: Position AFTER the move
            move: The move that was played

        Returns:
            True if move forks 2+ pieces
        """
        # Get the piece that moved
        piece = board.piece_at(move.to_square)
        if not piece:
            return False

        # Get all squares attacked by this piece
        attacked_squares = board.attacks(move.to_square)

        # Count valuable pieces attacked
        valuable_targets = []
        for sq in attacked_squares:
            target = board.piece_at(sq)
            if target and target.color != piece.color:
                # Consider pieces worth >= knight, or king
                if target.piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]:
                    valuable_targets.append(sq)

        # Fork = attacking 2+ valuable pieces (or piece + king)
        return len(valuable_targets) >= 2

    def _is_hanging_piece_capture(self, board: chess.Board, move: chess.Move) -> bool:
        """
        Check if a move captures an undefended piece.

        Args:
            board: Position AFTER the move
            move: The move that was played

        Returns:
            True if move captured a hanging piece
        """
        # Was this a capture?
        if not board.is_capture(move):
            # Check on the board BEFORE the move
            board_before = board.copy()
            board_before.pop()  # Undo the move
            if not board_before.is_capture(move):
                return False

        # Get the square where the capture happened
        capture_square = move.to_square

        # Check if the captured piece was defended
        # Go back one move to check original position
        board_before = board.copy()
        board_before.pop()

        captured_piece = board_before.piece_at(capture_square)
        if not captured_piece:
            return False

        # Count attackers and defenders of the capture square
        attackers = len(board_before.attackers(not captured_piece.color, capture_square))
        defenders = len(board_before.attackers(captured_piece.color, capture_square))

        # Hanging = more attackers than defenders
        return attackers > defenders


class EndgameClassifier:
    """
    Classifies endgame types based on remaining material.
    """

    def classify_endgame(self, board: chess.Board) -> Optional[Literal["pawn", "rook", "minor_piece", "queen", "mixed"]]:
        """
        Classify the type of endgame based on material.

        Args:
            board: Chess position to classify

        Returns:
            Endgame type or None if not an endgame
        """
        # Count pieces (excluding kings and pawns)
        piece_count = len(board.piece_map()) - 2  # Subtract 2 kings

        # Not an endgame if too many pieces
        if piece_count > 6:
            return None

        # Count piece types
        white_pieces = Counter()
        black_pieces = Counter()

        for square, piece in board.piece_map().items():
            if piece.piece_type == chess.KING:
                continue
            if piece.color == chess.WHITE:
                white_pieces[piece.piece_type] += 1
            else:
                black_pieces[piece.piece_type] += 1

        # Combine both sides
        all_pieces = white_pieces + black_pieces

        # Only pawns
        if set(all_pieces.keys()) == {chess.PAWN}:
            return "pawn"

        # Only rooks (and possibly pawns)
        non_pawn_pieces = {p for p in all_pieces.keys() if p != chess.PAWN}
        if non_pawn_pieces == {chess.ROOK}:
            return "rook"

        # Only minor pieces (knights/bishops)
        if non_pawn_pieces.issubset({chess.KNIGHT, chess.BISHOP}):
            return "minor_piece"

        # Queens present
        if chess.QUEEN in non_pawn_pieces:
            return "queen"

        # Mixed endgame
        if non_pawn_pieces:
            return "mixed"

        return None


def analyze_tactics_in_game(
    game: dict,
    move_evals: list[dict],
    blunder_indices_white: list[int],
    blunder_indices_black: list[int]
) -> dict:
    """
    Analyze all blunders in a game and classify their tactical patterns.

    Args:
        game: Game dictionary from Lichess
        move_evals: List of move evaluations from stockfish_eval.analyze_game_moves
        blunder_indices_white: Indices of white's blunders
        blunder_indices_black: Indices of black's blunders

    Returns:
        Dictionary with:
            - patterns_white: Counter of pattern types for white
            - patterns_black: Counter of pattern types for black
            - total_blunders_white: Total blunders by white
            - total_blunders_black: Total blunders by black
            - endgame_type: Type of endgame (if game reached endgame)
    """
    detector = TacticDetector()
    classifier = EndgameClassifier()

    patterns_white = Counter()
    patterns_black = Counter()

    # Reconstruct the game to analyze blunders
    board = chess.Board()
    move_list = game["moves"].split() if isinstance(game["moves"], str) else game["moves"]

    for i, move_san in enumerate(move_list):
        try:
            move = board.parse_san(move_san)
        except ValueError as e:
            # Skip invalid moves
            print(f"Warning: Skipping invalid move '{move_san}' at index {i}: {e}")
            break

        # Check if this was a blunder
        is_white = (i % 2 == 0)
        is_blunder = i in (blunder_indices_white if is_white else blunder_indices_black)

        if is_blunder:
            # Find the corresponding eval
            eval_entry = next((e for e in move_evals if e["move_index"] == i), None)

            if eval_entry:
                eval_before = eval_entry["eval_before"]
                eval_after = eval_entry["eval_after"]
                # best_move from eval_before is the best move from the position BEFORE the blunder
                best_move_uci = eval_before.get("best_move")

                if best_move_uci:
                    try:
                        best_move = chess.Move.from_uci(best_move_uci)
                        # Verify it's legal from this position
                        if best_move not in board.legal_moves:
                            # Skip invalid moves
                            continue

                        pattern = detector.classify_blunder_pattern(
                            board, move, best_move, eval_before, eval_after
                        )

                        if pattern:
                            if is_white:
                                patterns_white[pattern] += 1
                            else:
                                patterns_black[pattern] += 1
                        else:
                            # Unclassified blunder
                            if is_white:
                                patterns_white["unclassified"] += 1
                            else:
                                patterns_black["unclassified"] += 1
                    except ValueError:
                        # Invalid UCI, skip
                        pass

        board.push(move)

    # Classify final position endgame
    endgame_type = classifier.classify_endgame(board)

    return {
        "patterns_white": dict(patterns_white),
        "patterns_black": dict(patterns_black),
        "total_blunders_white": len(blunder_indices_white),
        "total_blunders_black": len(blunder_indices_black),
        "endgame_type": endgame_type
    }
