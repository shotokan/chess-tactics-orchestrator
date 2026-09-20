#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from chess_tactics_orchestrator.tools.lichess_client import LichessClient

client = LichessClient()

print("Testing isabido86...")
games = client.fetch_games("isabido86", max_games=5)
print(f"Fetched {len(games)} games")

if games:
    print(f"\nFirst game: {games[0].get('opening', {}).get('name', 'Unknown')}")
