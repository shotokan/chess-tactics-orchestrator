# Deployment Guide

## Prerequisites

- Python 3.11+
- uv package manager
- Gemini API key (free tier available at https://ai.google.dev/)
- Optional: Stockfish chess engine

## Quick Start

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup**:
   ```bash
   git clone <repo-url>
   cd chess-tactics-orchestrator
   uv sync
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your GEMINI_API_KEY
   ```

4. **Get your Gemini API key**:
   - Visit https://ai.google.dev/
   - Sign in with Google account
   - Create API key (free tier: 15 requests/minute, no credit card required)
   - Add to `.env`: `GEMINI_API_KEY=your_key_here`

5. **Run**:
   ```bash
   uv run chess-tactics DrNykterstein "How did I do with the Sicilian?"
   ```

## Using uv

This project uses `uv` for dependency management and execution:

- **Install dependencies**: `uv sync`
- **Run CLI**: `uv run chess-tactics <username> <question>`
- **Run tests**: `uv run pytest`
- **Add dependency**: `uv add <package>`
- **Update dependencies**: `uv sync --upgrade`

## Why Gemini?

- **Free tier**: 15 req/min, no credit card
- **Fast**: Gemini 2.0 Flash optimized for speed
- **Good quality**: Comparable to GPT-3.5/Haiku for structured tasks
- **Tool use**: Native support for function calling (used by research agent)

## Production Considerations

For production use:

1. **Rate limiting**: Free tier has 15 req/min limit. Add retry logic or upgrade plan.
2. **Stockfish**: Install for better move analysis (falls back to Lichess evals otherwise).
3. **Caching**: Lichess API responses could be cached to reduce latency.
4. **Async**: Convert to async execution for parallel game analysis.

## Troubleshooting

**Error: GEMINI_API_KEY not set**
- Ensure `.env` file exists with valid key

**Error: Stockfish not found**
- Install: `brew install stockfish` (macOS) or `apt-get install stockfish` (Linux)
- Or set `STOCKFISH_PATH` in `.env`

**Error: Module not found**
- Run `uv sync` to ensure all dependencies installed
- Check you're using `uv run` prefix for commands
