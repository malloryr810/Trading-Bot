"""
Tests for the FastAPI backend (app/api/).

All calls to analyze_stock are mocked — no network calls.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.analysis.fundamentals_analysis import FundamentalAnalysisError
from app.analysis.news_analysis import NewsAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport

_ANALYZE_STOCK = "app.api.routes.analysis.analyze_stock"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stock_report(ticker: str = "AAPL") -> StockReport:
    return StockReport(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=60.0,
        confidence_level=ConfidenceLevel.MEDIUM,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    from app.api.main import create_app
    return TestClient(create_app())


@pytest.fixture()
def mock_analyze_stock():
    with patch(_ANALYZE_STOCK, return_value=_make_stock_report()) as mock:
        yield mock


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_200(self, client):
        assert client.get("/api/health").status_code == 200

    def test_status_is_ok(self, client):
        assert client.get("/api/health").json()["status"] == "ok"

    def test_service_name(self, client):
        assert client.get("/api/health").json()["service"] == "investment-bot-api"


# ---------------------------------------------------------------------------
# POST /api/analyze — success path
# ---------------------------------------------------------------------------

class TestAnalyzeSuccess:
    def test_returns_200(self, client, mock_analyze_stock):
        assert client.post("/api/analyze", json={"ticker": "AAPL"}).status_code == 200

    def test_calls_analyze_stock_with_ticker(self, client, mock_analyze_stock):
        client.post("/api/analyze", json={"ticker": "AAPL"})
        mock_analyze_stock.assert_called_once_with("AAPL")

    def test_response_contains_ticker(self, client, mock_analyze_stock):
        data = client.post("/api/analyze", json={"ticker": "AAPL"}).json()
        assert data["ticker"] == "AAPL"

    def test_response_contains_score(self, client, mock_analyze_stock):
        data = client.post("/api/analyze", json={"ticker": "AAPL"}).json()
        assert data["score"] == 60.0

    def test_response_contains_final_category(self, client, mock_analyze_stock):
        data = client.post("/api/analyze", json={"ticker": "AAPL"}).json()
        assert data["final_category"] == RatingCategory.WATCHLIST.value

    def test_response_contains_confidence_level(self, client, mock_analyze_stock):
        data = client.post("/api/analyze", json={"ticker": "AAPL"}).json()
        assert data["confidence_level"] == ConfidenceLevel.MEDIUM.value


# ---------------------------------------------------------------------------
# POST /api/analyze — ticker normalization
# ---------------------------------------------------------------------------

class TestAnalyzeTickerNormalization:
    def test_lowercase_ticker_is_uppercased(self, client, mock_analyze_stock):
        client.post("/api/analyze", json={"ticker": "aapl"})
        mock_analyze_stock.assert_called_once_with("AAPL")

    def test_mixed_case_ticker_is_uppercased(self, client, mock_analyze_stock):
        client.post("/api/analyze", json={"ticker": "AaPl"})
        mock_analyze_stock.assert_called_once_with("AAPL")

    def test_ticker_with_leading_trailing_whitespace_is_stripped(self, client, mock_analyze_stock):
        client.post("/api/analyze", json={"ticker": " AAPL "})
        mock_analyze_stock.assert_called_once_with("AAPL")

    def test_lowercase_with_whitespace_normalized(self, client, mock_analyze_stock):
        client.post("/api/analyze", json={"ticker": " aapl "})
        mock_analyze_stock.assert_called_once_with("AAPL")


# ---------------------------------------------------------------------------
# POST /api/analyze — invalid input
# ---------------------------------------------------------------------------

class TestAnalyzeInvalidInput:
    def test_empty_ticker_returns_422(self, client):
        assert client.post("/api/analyze", json={"ticker": ""}).status_code == 422

    def test_whitespace_only_ticker_returns_422(self, client):
        assert client.post("/api/analyze", json={"ticker": "   "}).status_code == 422

    def test_missing_ticker_field_returns_422(self, client):
        assert client.post("/api/analyze", json={}).status_code == 422

    def test_non_string_ticker_returns_422(self, client):
        assert client.post("/api/analyze", json={"ticker": 123}).status_code == 422


# ---------------------------------------------------------------------------
# POST /api/analyze — known service errors map to 422
# ---------------------------------------------------------------------------

class TestAnalyzeKnownErrors:
    def test_data_fetch_error_returns_422(self, client):
        with patch(_ANALYZE_STOCK, side_effect=DataFetchError("ticker not found")):
            response = client.post("/api/analyze", json={"ticker": "INVALID"})
        assert response.status_code == 422
        assert "ticker not found" in response.json()["detail"]

    def test_fundamental_data_error_returns_422(self, client):
        with patch(_ANALYZE_STOCK, side_effect=FundamentalDataFetchError("no fundamentals")):
            response = client.post("/api/analyze", json={"ticker": "AAPL"})
        assert response.status_code == 422

    def test_technical_analysis_error_returns_422(self, client):
        with patch(_ANALYZE_STOCK, side_effect=TechnicalAnalysisError("cannot compute")):
            response = client.post("/api/analyze", json={"ticker": "AAPL"})
        assert response.status_code == 422

    def test_risk_analysis_error_returns_422(self, client):
        with patch(_ANALYZE_STOCK, side_effect=RiskAnalysisError("risk failed")):
            response = client.post("/api/analyze", json={"ticker": "AAPL"})
        assert response.status_code == 422

    def test_news_analysis_error_returns_422(self, client):
        with patch(_ANALYZE_STOCK, side_effect=NewsAnalysisError("news failed")):
            response = client.post("/api/analyze", json={"ticker": "AAPL"})
        assert response.status_code == 422

    def test_scoring_error_returns_422(self, client):
        with patch(_ANALYZE_STOCK, side_effect=ScoringError("scoring failed")):
            response = client.post("/api/analyze", json={"ticker": "AAPL"})
        assert response.status_code == 422

    def test_known_error_detail_is_string(self, client):
        with patch(_ANALYZE_STOCK, side_effect=DataFetchError("some error")):
            response = client.post("/api/analyze", json={"ticker": "AAPL"})
        assert isinstance(response.json()["detail"], str)


# ---------------------------------------------------------------------------
# POST /api/analyze — unexpected errors map to 500
# ---------------------------------------------------------------------------

class TestAnalyzeUnexpectedErrors:
    def test_unexpected_exception_returns_500(self, client):
        with patch(_ANALYZE_STOCK, side_effect=RuntimeError("unexpected")):
            response = client.post("/api/analyze", json={"ticker": "AAPL"})
        assert response.status_code == 500

    def test_500_response_has_detail_key(self, client):
        with patch(_ANALYZE_STOCK, side_effect=ValueError("something broke")):
            response = client.post("/api/analyze", json={"ticker": "AAPL"})
        assert "detail" in response.json()


# ---------------------------------------------------------------------------
# CORS — local frontend origins
# ---------------------------------------------------------------------------

class TestCors:
    def test_allowed_origin_gets_cors_header(self, client):
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_preflight_from_local_frontend_is_allowed(self, client):
        response = client.options(
            "/api/analyze",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_unknown_origin_is_not_reflected(self, client):
        response = client.get(
            "/api/health",
            headers={"Origin": "http://evil.com"},
        )
        assert response.headers.get("access-control-allow-origin") is None
