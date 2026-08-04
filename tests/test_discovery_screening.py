"""
Tests for app/services/discovery_screening.py.

``get_price_history`` is patched in every test, so the pre-screen is exercised
against locally built DataFrames — never a live provider call.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from app.data.market_data import DataFetchError
from app.services.discovery_screening import (
    MIN_HISTORY_ROWS,
    prescreen_ticker,
)

_FETCH = "app.services.discovery_screening.get_price_history"


def _history(rows: int = MIN_HISTORY_ROWS, close: float = 100.0, volume: float = 1_000_000.0):
    index = pd.date_range("2026-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "open": [close] * rows,
            "high": [close] * rows,
            "low": [close] * rows,
            "close": [close] * rows,
            "volume": [volume] * rows,
        },
        index=index,
    )


class TestPrescreenPasses:
    def test_healthy_history_passes(self):
        with patch(_FETCH, return_value=_history()):
            assert prescreen_ticker("AAPL").passed is True

    def test_passing_result_has_no_reason(self):
        with patch(_FETCH, return_value=_history(rows=200)):
            assert prescreen_ticker("AAPL").reason is None

    def test_result_echoes_the_ticker(self):
        with patch(_FETCH, return_value=_history()):
            assert prescreen_ticker("AAPL").ticker == "AAPL"


    def test_in_progress_session_row_is_ignored(self):
        # The provider returns a row for the current session with volume but no
        # settled OHLC; that must not read as "no valid price".
        history = _history(rows=MIN_HISTORY_ROWS + 1)
        history.iloc[-1, history.columns.get_indexer(["open", "high", "low", "close"])] = (
            float("nan")
        )
        with patch(_FETCH, return_value=history):
            assert prescreen_ticker("AAPL").passed is True

    def test_settled_rows_must_still_meet_the_minimum(self):
        history = _history(rows=MIN_HISTORY_ROWS)
        history.iloc[-1, history.columns.get_indexer(["close"])] = float("nan")
        with patch(_FETCH, return_value=history):
            result = prescreen_ticker("AAPL")
        assert result.passed is False
        assert "settled price rows" in result.reason


class TestPrescreenRejections:
    def test_short_history_fails(self):
        with patch(_FETCH, return_value=_history(rows=MIN_HISTORY_ROWS - 1)):
            result = prescreen_ticker("AAPL")
        assert result.passed is False
        assert "price rows" in result.reason

    def test_non_positive_close_fails(self):
        with patch(_FETCH, return_value=_history(close=0.0)):
            result = prescreen_ticker("AAPL")
        assert result.passed is False
        assert "close" in result.reason

    def test_zero_volume_fails(self):
        with patch(_FETCH, return_value=_history(volume=0.0)):
            result = prescreen_ticker("AAPL")
        assert result.passed is False
        assert "volume" in result.reason

    def test_data_fetch_error_fails_without_raising(self):
        with patch(_FETCH, side_effect=DataFetchError("delisted")):
            result = prescreen_ticker("BADTICKER")
        assert result.passed is False
        assert "delisted" in result.reason

    def test_unexpected_provider_error_fails_without_raising(self):
        with patch(_FETCH, side_effect=RuntimeError("provider exploded")):
            result = prescreen_ticker("AAPL")
        assert result.passed is False
        assert result.reason

    @pytest.mark.parametrize("exc", [DataFetchError("x"), RuntimeError("y"), ValueError("z")])
    def test_no_provider_error_propagates(self, exc):
        with patch(_FETCH, side_effect=exc):
            assert prescreen_ticker("AAPL").passed is False
