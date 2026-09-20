#!/usr/bin/env python3
"""Test blunder detection with a small sample."""
import sys
sys.path.insert(0, 'src')

from chess_tactics_orchestrator.tools.lichess_client import LichessClient
from chess_tactics_orchestrator.tools.stockfish_eval import StockfishEvaluator, analyze_game_moves

client = LichessClient()

print("Fetching 20 games...")
games = client.fetch_games("isabido86", max_games=20, with_analysis=True)
print(f"Fetched {len(games)} games\n")

if not games:
    print("No games found!")
    sys.exit(1)

total_blunders_white = 0
total_blunders_black = 0
games_analyzed = 0

print("Analyzing games for blunders (threshold=75cp)...")
with StockfishEvaluator() as evaluator:
    for idx, game in enumerate(games[:10], 1):
        print(f"\n[{idx}/10] Game: {game.get('id', 'unknown')} - {game.get('opening', {}).get('name', 'Unknown')}")

        result = analyze_game_moves(game, evaluator, sample_every_n_moves=3, debug=False)

        white_blunders = len(result['blunders_white'])
        black_blunders = len(result['blunders_black'])

        print(f"  Blunders: white={white_blunders}, black={black_blunders}")
        print(f"  Evals: lichess={result['lichess_eval_count']}, stockfish={result['stockfish_eval_count']}")

        total_blunders_white += white_blunders
        total_blunders_black += black_blunders
        games_analyzed += 1

print("\n" + "="*60)
print(f"TOTAL across {games_analyzed} games:")
print(f"  White blunders: {total_blunders_white}")
print(f"  Black blunders: {total_blunders_black}")
print(f"  Average per game: {(total_blunders_white + total_blunders_black) / games_analyzed:.1f}")
