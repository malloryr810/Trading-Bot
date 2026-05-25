"""
General-purpose helpers.

Small, stateless utility functions reused across modules:
ticker normalization and safe numeric conversions.
"""

import math


def safe_float(value: object) -> float | None:
    """Return float if value is a finite number, else None."""
    try:
        f = float(value)  # type: ignore[arg-type]
        return None if not math.isfinite(f) else f
    except (TypeError, ValueError):
        return None


def normalize_ticker(ticker: object) -> str:
    """Validate and normalize a ticker symbol to uppercase with whitespace stripped.

    Args:
        ticker: Value to validate and normalize.

    Returns:
        The uppercased, stripped ticker string.

    Raises:
        ValueError: If ticker is not a string, is empty, or is whitespace-only.
    """
    if not isinstance(ticker, str):
        raise ValueError(
            f"Ticker must be a string, got {type(ticker).__name__}."
        )
    stripped = ticker.strip()
    if not stripped:
        raise ValueError("Ticker must not be empty or whitespace.")
    return stripped.upper()
