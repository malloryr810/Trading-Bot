"""
Discovery stage-1 pre-screen.

A deliberately lightweight validity check applied to universe tickers *before*
the expensive full analysis pipeline runs. It answers one question only: "is
there enough usable price data here for the analysis engine to say anything
meaningful?" It computes no signals, no scores, and no rankings.

The pre-screen exists so the shortlist stays bounded as universes grow — full
analysis is only ever run on tickers that already passed this check.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.data.market_data import DataFetchError, get_price_history
from app.utils.helpers import safe_float

# Enough daily bars for the technical layer to produce non-degenerate signals.
# Deliberately below the 200-bar SMA window: the analysis modules already emit
# neutral low-confidence signals for shorter histories, so this is a floor for
# "usable at all", not a quality bar.
MIN_HISTORY_ROWS = 60

# Short window — the pre-screen only needs recency and shape, not a full year.
PRESCREEN_PERIOD = "6mo"
PRESCREEN_INTERVAL = "1d"


@dataclass(frozen=True)
class PrescreenResult:
    """Outcome of the stage-1 check for one ticker."""

    ticker: str
    passed: bool
    reason: str | None = None


def prescreen_ticker(ticker: str) -> PrescreenResult:
    """Check that a ticker has usable recent price data.

    Passing requires: a fetchable price history, at least ``MIN_HISTORY_ROWS``
    daily bars with a settled close, a positive finite latest settled close, and
    a positive average volume. An in-progress trading session (the provider
    returns a row whose OHLC values are still null) is ignored rather than
    treated as a failure. Any fetch or validation failure is returned as a failed
    result — it is never raised, so one bad ticker cannot abort a discovery run.

    Args:
        ticker: Ticker symbol from the universe (already normalized upstream).

    Returns:
        A PrescreenResult with ``passed`` and, on failure, a short ``reason``.
    """
    try:
        history = get_price_history(
            ticker, period=PRESCREEN_PERIOD, interval=PRESCREEN_INTERVAL
        )
    except DataFetchError as exc:
        return PrescreenResult(ticker, False, f"No usable price history: {exc}")
    except Exception as exc:  # defensive: provider errors must not abort the run
        return PrescreenResult(
            ticker, False, f"Price history unavailable: {exc or type(exc).__name__}"
        )

    # The provider often returns a partially formed row for the current session
    # (volume present, OHLC still null), so work from the settled closes only.
    closes = history["close"].dropna()

    if len(closes) < MIN_HISTORY_ROWS:
        return PrescreenResult(
            ticker,
            False,
            f"Only {len(closes)} settled price rows available; "
            f"{MIN_HISTORY_ROWS} required for analysis.",
        )

    last_close = safe_float(closes.iloc[-1])
    if last_close is None or last_close <= 0:
        return PrescreenResult(
            ticker, False, "Most recent settled close price is not positive."
        )

    average_volume = safe_float(history["volume"].mean())
    if average_volume is None or average_volume <= 0:
        return PrescreenResult(ticker, False, "No usable average volume.")

    return PrescreenResult(ticker, True)
