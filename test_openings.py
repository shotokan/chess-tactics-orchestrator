#!/usr/bin/env python3
"""Quick test to see what openings are returned from Lichess API."""

import requests
import json
import time

username = "isabido86"
# Correct endpoint according to Lichess API docs
url = f"https://lichess.org/api/user/{username}/games"

# Test 1: Get games with black pieces
print("=" * 60)
print("TEST 1: Games with BLACK pieces (with 2s delay)")
print("=" * 60)

time.sleep(2)

params = {
    "max": 50,
    "opening": "true",
    "color": "black",
    "pgnInJson": "true"
}

response = requests.get(url, params=params, headers={"Accept": "application/x-ndjson"})
print(f"Status: {response.status_code}")

if response.status_code == 200:
    games = []
    for line in response.text.strip().split('\n'):
        if line:
            games.append(json.loads(line))

    print(f"Total games: {len(games)}")

    # Count openings
    openings = {}
    sicilian_games = []

    for game in games:
        opening_name = game.get("opening", {}).get("name", "Unknown")
        openings[opening_name] = openings.get(opening_name, 0) + 1

        if "sicilian" in opening_name.lower():
            sicilian_games.append(game)

    print(f"\nTop 10 openings:")
    for opening, count in sorted(openings.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {opening}: {count}")

    print(f"\nSicilian games found: {len(sicilian_games)}")
    if sicilian_games:
        print("Details:")
        for game in sicilian_games[:3]:
            white = game["players"]["white"]["user"]["name"]
            black = game["players"]["black"]["user"]["name"]
            opening = game.get("opening", {}).get("name", "Unknown")
            print(f"  - {white} vs {black}: {opening}")
else:
    print(f"Error: {response.text}")

# Test 2: Get games WITHOUT color filter
print("\n" + "=" * 60)
print("TEST 2: Games WITHOUT color filter (with 2s delay)")
print("=" * 60)

time.sleep(2)

params2 = {
    "max": 50,
    "opening": "true",
    "pgnInJson": "true"
}

response2 = requests.get(url, params=params2, headers={"Accept": "application/x-ndjson"})
print(f"Status: {response2.status_code}")

if response2.status_code == 200:
    games2 = []
    for line in response2.text.strip().split('\n'):
        if line:
            games2.append(json.loads(line))

    print(f"Total games: {len(games2)}")

    # Count Sicilian by color
    sicilian_as_white = 0
    sicilian_as_black = 0

    for game in games2:
        opening_name = game.get("opening", {}).get("name", "")
        if "sicilian" in opening_name.lower():
            white_user = game["players"]["white"]["user"]["name"].lower()
            black_user = game["players"]["black"]["user"]["name"].lower()

            if white_user == username.lower():
                sicilian_as_white += 1
                print(f"  WHITE: {opening_name}")
            elif black_user == username.lower():
                sicilian_as_black += 1
                print(f"  BLACK: {opening_name}")

    print(f"\nSicilian as WHITE: {sicilian_as_white}")
    print(f"Sicilian as BLACK: {sicilian_as_black}")
else:
    print(f"Error: {response2.text}")
