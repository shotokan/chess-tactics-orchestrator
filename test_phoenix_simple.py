#!/usr/bin/env python3
"""
Simple Phoenix test without full graph execution.

Tests basic instrumentation and custom spans.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, 'src')

from chess_tactics_orchestrator.observability import setup_observability, get_phoenix_tracer

print("=" * 60)
print("Testing Phoenix Observability - Simple Trace")
print("=" * 60)

# Setup Phoenix
print("\n[1/3] Setting up Phoenix...")
setup_observability()

# Test custom span
print("\n[2/3] Creating custom span...")
phoenix = get_phoenix_tracer()

with phoenix.span("test_operation", {"test_attr": "hello", "count": 42}):
    print("  Inside span: test_operation")

    with phoenix.span("nested_operation", {"nested": True}):
        print("  Inside nested span: nested_operation")

print("✓ Spans created")

# Test LangChain instrumentation
print("\n[3/3] Testing LangChain instrumentation...")

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

api_key = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", google_api_key=api_key)

response = llm.invoke([HumanMessage(content="Say 'test OK' in Spanish")])
print(f"  LLM response: {response.content}")

print("\n=" * 60)
print("✅ Test completed!")
print("\nView traces at: http://localhost:6006")
print("  Project: chess-tactics-orchestrator")
print("=" * 60)
