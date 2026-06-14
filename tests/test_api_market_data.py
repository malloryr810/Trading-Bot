"""
Tests for GET /api/market-data/{ticker}/history.

The data-layer fetch (app.data.market_data.get_price_history) is mocked
everywhere — no network calls. Deterministic DataFrames are built locally.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.data.market_data import DataFetchError

# Patch the name as imported into the service module.
_GET_PRICE_HISTORY = "app.services.market_data_service.get_price_history"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_price_df() -> pd.DataFrame:
    index = pd.to_datetime(["2025-06-10", "2025-06-11", "2025-06-12"])
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [104.0, 105.5, 106.0],
            "volume": [1_000_000, 1_200_000, 900_000],
        },
        index=index,
    )


@pytest.fixture()
def client():
    from app.api.main import create_app

    return TestClient(create_app())


@pytest.fixture()
def mock_history():
    with patch(_GET_PRICE_HISTORY, return_value=_make_price_df()) as mock:
        yield mock


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

class TestHistorySuccess:
    def test_returns_200(self, client, mock_history):
        assert client.get("/api/market-data/AAPL/history").status_code == 200

    def test_response_ticker_is_uppercased(self, client, mock_history):
        data = client.get("/api/market-data/aapl/history").json()
        assert data["ticker"] == "AAPL"

    def test_echoes_default_period_and_interval(self, client, mock_history):
        data = client.get("/api/market-data/AAPL/history").json()
        assert data["period"] == "1y"
        assert data["interval"] == "1d"

    def test_returns_all_price_points(self, client, mock_history):
        data = client.get("/api/market-data/AAPL/history").json()
        assert len(data["prices"]) == 3

    def test_first_point_fields(self, client, mock_history):
        point = client.get("/api/market-data/AAPL/history").json()["prices"][0]
        assert point["date"] == "2025-06-10"
        assert point["close"] == 104.0
        assert point["open"] == 100.0
        assert point["volume"] == 1_000_000.0

    def test_data_timestamp_is_last_row(self, client, mock_history):
        data = client.get("/api/market-data/AAPL/history").json()
        assert data["data_timestamp"].startswith("2025-06-12")


# ---------------------------------------------------------------------------
# Parameter handling
# ---------------------------------------------------------------------------

class TestHistoryParameters:
    def test_default_params_passed_to_data_layer(self, client, mock_history):
        client.get("/api/market-data/AAPL/history")
        mock_history.assert_called_once_with("AAPL", period="1y", interval="1d")

    def test_custom_valid_params_passed_through(self, client, mock_history):
        client.get("/api/market-data/MSFT/history?period=6mo&interval=1wk")
        mock_history.assert_called_once_with("MSFT", period="6mo", interval="1wk")

    def test_uppercase_period_is_normalized(self, client, mock_history):
        client.get("/api/market-data/AAPL/history?period=1Y")
        mock_history.assert_called_once_with("AAPL", period="1y", interval="1d")

    def test_invalid_period_returns_422(self, client, mock_history):
        response = client.get("/api/market-data/AAPL/history?period=banana")
        assert response.status_code == 422
        assert "period" in response.json()["detail"]

    def test_invalid_interval_returns_422(self, client, mock_history):
        response = client.get("/api/market-data/AAPL/history?interval=1m")
        assert response.status_code == 422
        assert "interval" in response.json()["detail"]

    def test_invalid_params_do_not_hit_data_layer(self, client, mock_history):
        client.get("/api/market-data/AAPL/history?period=banana")
        mock_history.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestHistoryErrors:
    def test_data_fetch_error_returns_422(self, client):
        with patch(_GET_PRICE_HISTORY, side_effect=DataFetchError("invalid symbol")):
            response = client.get("/api/market-data/NOPE/history")
        assert response.status_code == 422
        assert "invalid symbol" in response.json()["detail"]

    def test_empty_data_returns_422(self, client):
        with patch(
            _GET_PRICE_HISTORY,
            side_effect=DataFetchError("No data returned by yfinance"),
        ):
            response = client.get("/api/market-data/AAPL/history")
        assert response.status_code == 422

    def test_unexpected_error_returns_500(self, client):
        with patch(_GET_PRICE_HISTORY, side_effect=RuntimeError("boom")):
            response = client.get("/api/market-data/AAPL/history")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_error_detail_is_string(self, client):
        with patch(_GET_PRICE_HISTORY, side_effect=DataFetchError("bad")):
            response = client.get("/api/market-data/AAPL/history")
        assert isinstance(response.json()["detail"], str)


# ---------------------------------------------------------------------------
# JSON safety — non-finite values become null
# ---------------------------------------------------------------------------

class TestHistoryJsonSafety:
    def test_nan_values_serialize_as_null(self, client):
        index = pd.to_datetime(["2025-06-10", "2025-06-11"])
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [104.0, np.nan],
                "volume": [1_000_000, np.nan],
            },
            index=index,
        )
        with patch(_GET_PRICE_HISTORY, return_value=df):
            response = client.get("/api/market-data/AAPL/history")
        assert response.status_code == 200
        point = response.json()["prices"][1]
        assert point["close"] is None
        assert point["volume"] is None
