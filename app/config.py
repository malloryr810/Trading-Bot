"""
Central configuration module.

Loads environment variables from an optional local ``.env`` file (never
committed) via python-dotenv. yfinance — the only data provider — needs no API
key, so the database path is the only setting today. Add any future secret
here rather than calling ``os.getenv`` throughout the codebase.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Database ---
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/investment_bot.db")
