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
# Reserved placeholders. The only data provider in use today is yfinance, which
# needs no key, so nothing reads these yet — they exist so a keyed provider can
# be added without scattering os.getenv calls through the data layer.
MARKET_DATA_API_KEY: str = os.getenv("MARKET_DATA_API_KEY", "")
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")

# --- Runtime environment ---
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

# --- Database ---
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/investment_bot.db")
