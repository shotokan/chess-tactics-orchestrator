#!/usr/bin/env python3
import os
from langchain_google_genai import ChatGoogleGenerativeAI

api_key = os.getenv("GEMINI_API_KEY", "")

# Try common models
models = [
    "gemini-pro",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-2.0-flash-exp",
    "models/gemini-pro",
    "models/gemini-1.5-flash",
]

for model in models:
    try:
        llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key)
        response = llm.invoke("Hi")
        print(f"✓ {model} works")
        break
    except Exception as e:
        print(f"✗ {model}: {str(e)[:100]}")
