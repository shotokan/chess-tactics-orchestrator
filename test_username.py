#!/usr/bin/env python3
"""Test username extraction logic."""
import sys
sys.path.insert(0, 'src')

from chess_tactics_orchestrator.tools.lichess_client import LichessClient

client = LichessClient()

print("Fetching 5 Sicilian games with black...")
games = client.fetch_games("isabido86", max_games=200, color="black", with_analysis=True)
games = client.filter_by_opening(games, "Sicilian")
print(f"Found {len(games)} Sicilian games with black\n")

if len(games) >= 2:
    first = games[0]
    last = games[-1]

    w1 = first.get("players", {}).get("white", {}).get("user", {}).get("name")
    b1 = first.get("players", {}).get("black", {}).get("user", {}).get("name")
    w_last = last.get("players", {}).get("white", {}).get("user", {}).get("name")
    b_last = last.get("players", {}).get("black", {}).get("user", {}).get("name")

    print(f"First game: white={w1}, black={b1}")
    print(f"Last game: white={w_last}, black={b_last}")
    print()

    # Test extraction logic
    username = "unknown"
    if w1 and (w1 == w_last or w1 == b_last):
        username = w1
    elif b1 and (b1 == w_last or b1 == b_last):
        username = b1
    else:
        username = w1 or b1 or "unknown"

    print(f"Extracted username: {username}")
    print(f"Expected: isabido86")
