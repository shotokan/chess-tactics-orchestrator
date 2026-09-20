#!/usr/bin/env python3
"""Test Lichess API with berserk library."""

import berserk

# Create a client (no token needed for public games)
client = berserk.Client()

username = "DrNykterstein"  # Magnus Carlsen - public account

print(f"Fetching games for {username}...")

try:
    games = client.games.export_by_player(username, max=5, evals=True, opening=True)

    count = 0
    for game in games:
        count += 1
        white = game["players"]["white"]["user"]["name"]
        black = game["players"]["black"]["user"]["name"]
        opening = game.get("opening", {}).get("name", "Unknown")
        print(f"{count}. {white} vs {black}: {opening}")

        if count >= 5:
            break

    print(f"\n✓ Successfully fetched {count} games")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
