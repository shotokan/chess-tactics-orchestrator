#!/usr/bin/env python3
"""
Simple checkpoint test - just verify RedisSaver creation.
"""

import sys
sys.path.insert(0, 'src')

from chess_tactics_orchestrator.infrastructure import create_redis_checkpointer

print("Testing RedisSaver creation...")

try:
    checkpointer = create_redis_checkpointer(host="localhost", port=6379)
    print(f"✓ RedisSaver created: {checkpointer}")
    print(f"  Type: {type(checkpointer)}")
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
