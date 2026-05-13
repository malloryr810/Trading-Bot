"""
Central configuration module.

Loads environment variables via python-dotenv and exposes typed
settings consumed by data fetchers, analysis modules, and utilities.
Add real values to a local .env file (never committed to version control).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API keys (set in .env, never hardcoded) ---
MARKET_DATA_API_KEY: str = os.getenv("MARKET_DATA_API_KEY", "")
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# --- Database ---
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# --- Runtime environment ---
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
DEBUG: bool = ENVIRONMENT == "development"
