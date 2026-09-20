#!/usr/bin/env python3
"""Verify if Lichess user exists."""

import requests
import time

# Try different variations of the username
usernames = ["isabido86", "Isabido86", "ISABIDO86", "isabido"]

for username in usernames:
    print(f"\nTesting: {username}")

    # Try games endpoint
    url = f"https://lichess.org/api/games/user/{username}"
    time.sleep(1)

    response = requests.get(
        url,
        params={"max": 1, "pgnInJson": "true"},
        headers={"Accept": "application/x-ndjson"}
    )

    print(f"  Games API status: {response.status_code}")

    if response.status_code == 200:
        print(f"  ✓ Found user: {username}")
        print(f"  Response preview: {response.text[:200]}")
        break

    # Try user API
    user_url = f"https://lichess.org/api/user/{username}"
    time.sleep(1)

    response2 = requests.get(user_url, headers={"Accept": "application/json"})
    print(f"  User API status: {response2.status_code}")

    if response2.status_code == 200:
        import json
        user_data = response2.json()
        print(f"  ✓ User found via user API")
        print(f"    Username: {user_data.get('username')}")
        print(f"    ID: {user_data.get('id')}")
