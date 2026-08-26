"""
Tests for /api/reports/* endpoints.

analyze_stock and all persistence service functions are mocked — no network
calls and no real database writes.  The existing /api/analyze endpoint is
also tested to confirm it does not trigger any persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.analysis.news_analysis import NewsAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport

# Patch targets — functions as imported inside the route module
_ANALYZE_STOCK = "app.api.routes.reports.analyze_stock"
_ANALYZE_STOCK_ANALYSIS = "app.api.routes.analysis.analyze_stock"
_SAVE = "app.api.routes.reports.save_stock_report"
_LIST = "app.api.routes.reports.list_saved_reports"
_GET = "app.api.routes.reports.get_saved_report"

_CREATED_AT = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stock_report(ticker: str = "AAPL") -> StockReport:
    return StockReport(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=60.0,
        confidence_level=ConfidenceLevel.MEDIUM,
        company_name="Apple Inc.",
    )


def _make_summary(report_id: int = 1, ticker: str = "AAPL") -> dict:
    return {
        "id": report_id,
        "ticker": ticker,
        "company_name": "Apple Inc.",
        "category": RatingCategory.WATCHLIST.value,
        "score": 60.0,
        "confidence": ConfidenceLevel.MEDIUM.value,
        "created_at": _CREATED_AT,
    }


def _make_detail(report_id: int = 1, ticker: str = "AAPL") -> dict:
    report = _make_stock_report(ticker)
    return {**_make_summary(report_id, ticker), "report": report.model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    from app.api.main import create_app
    return TestClient(create_app())


@pytest.fixture()
def mock_analyze():
    with patch(_ANALYZE_STOCK, return_value=_make_stock_report()) as m:
        yield m


@pytest.fixture()
def mock_save():
    with patch(_SAVE, return_value=_make_detail()) as m:
        yield m


@pytest.fixture()
def mock_list():
    with patch(_LIST, return_value=[_make_summary()]) as m:
        yield m


@pytest.fixture()
def mock_get():
    with patch(_GET, return_value=_make_detail()) as m:
        yield m


# ---------------------------------------------------------------------------
# POST /api/reports/analyze — success path
# ---------------------------------------------------------------------------


class TestAnalyzeAndSaveSuccess:
    def test_returns_200(self, client, mock_analyze, mock_save):
        assert client.post("/api/reports/analyze", json={"ticker": "AAPL"}).status_code == 200

    def test_calls_analyze_stock_with_ticker(self, client, mock_analyze, mock_save):
        client.post("/api/reports/analyze", json={"ticker": "AAPL"})
        mock_analyze.assert_called_once_with("AAPL")

    def test_calls_save_stock_report(self, client, mock_analyze, mock_save):
        client.post("/api/reports/analyze", json={"ticker": "AAPL"})
        mock_save.assert_called_once()

    def test_save_receives_stock_report(self, client, mock_analyze, mock_save):
        client.post("/api/reports/analyze", json={"ticker": "AAPL"})
        args, _ = mock_save.call_args
        assert isinstance(args[0], StockReport)

    def test_response_has_id(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert "id" in data

    def test_response_id_value(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert data["id"] == 1

    def test_response_has_ticker(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert data["ticker"] == "AAPL"

    def test_response_has_category(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert data["category"] == RatingCategory.WATCHLIST.value

    def test_response_has_score(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert data["score"] == 60.0

    def test_response_has_confidence(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert data["confidence"] == ConfidenceLevel.MEDIUM.value

    def test_response_has_created_at(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert "created_at" in data

    def test_response_has_report(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert "report" in data

    def test_response_report_is_dict(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert isinstance(data["report"], dict)

    def test_response_report_ticker(self, client, mock_analyze, mock_save):
        data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert data["report"]["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# POST /api/reports/analyze — ticker normalization
# ---------------------------------------------------------------------------


class TestAnalyzeAndSaveTickerNormalization:
    def test_lowercase_ticker_is_uppercased(self, client, mock_analyze, mock_save):
        client.post("/api/reports/analyze", json={"ticker": "aapl"})
        mock_analyze.assert_called_once_with("AAPL")

    def test_mixed_case_ticker_is_uppercased(self, client, mock_analyze, mock_save):
        client.post("/api/reports/analyze", json={"ticker": "AaPl"})
        mock_analyze.assert_called_once_with("AAPL")

    def test_whitespace_is_stripped(self, client, mock_analyze, mock_save):
        client.post("/api/reports/analyze", json={"ticker": " AAPL "})
        mock_analyze.assert_called_once_with("AAPL")


# ---------------------------------------------------------------------------
# POST /api/reports/analyze — invalid input
# ---------------------------------------------------------------------------


class TestAnalyzeAndSaveInvalidInput:
    def test_empty_ticker_returns_422(self, client):
        assert client.post("/api/reports/analyze", json={"ticker": ""}).status_code == 422

    def test_whitespace_only_ticker_returns_422(self, client):
        assert client.post("/api/reports/analyze", json={"ticker": "   "}).status_code == 422

    def test_missing_ticker_returns_422(self, client):
        assert client.post("/api/reports/analyze", json={}).status_code == 422

    def test_non_string_ticker_returns_422(self, client):
        assert client.post("/api/reports/analyze", json={"ticker": 123}).status_code == 422


# ---------------------------------------------------------------------------
# POST /api/reports/analyze — known service errors → 422
# ---------------------------------------------------------------------------


class TestAnalyzeAndSaveKnownErrors:
    def _post(self, client, side_effect):
        with patch(_ANALYZE_STOCK, side_effect=side_effect):
            return client.post("/api/reports/analyze", json={"ticker": "INVALID"})

    def test_data_fetch_error_returns_422(self, client):
        assert self._post(client, DataFetchError("no data")).status_code == 422

    def test_fundamental_data_error_returns_422(self, client):
        assert self._post(client, FundamentalDataFetchError("no fundamentals")).status_code == 422

    def test_technical_error_returns_422(self, client):
        assert self._post(client, TechnicalAnalysisError("no technicals")).status_code == 422

    def test_risk_error_returns_422(self, client):
        assert self._post(client, RiskAnalysisError("no risk")).status_code == 422

    def test_news_error_returns_422(self, client):
        assert self._post(client, NewsAnalysisError("no news")).status_code == 422

    def test_scoring_error_returns_422(self, client):
        assert self._post(client, ScoringError("scoring failed")).status_code == 422

    def test_known_error_does_not_call_save(self, client):
        with patch(_ANALYZE_STOCK, side_effect=DataFetchError("no data")), \
             patch(_SAVE) as mock_save:
            client.post("/api/reports/analyze", json={"ticker": "INVALID"})
        mock_save.assert_not_called()

    def test_known_error_detail_is_string(self, client):
        with patch(_ANALYZE_STOCK, side_effect=DataFetchError("some error")):
            data = client.post("/api/reports/analyze", json={"ticker": "X"}).json()
        assert isinstance(data["detail"], str)


# ---------------------------------------------------------------------------
# POST /api/reports/analyze — unexpected errors → 500
# ---------------------------------------------------------------------------


class TestAnalyzeAndSaveUnexpectedErrors:
    def test_runtime_error_returns_500(self, client):
        with patch(_ANALYZE_STOCK, side_effect=RuntimeError("crash")):
            assert client.post("/api/reports/analyze", json={"ticker": "AAPL"}).status_code == 500

    def test_500_does_not_call_save(self, client):
        with patch(_ANALYZE_STOCK, side_effect=RuntimeError("crash")), \
             patch(_SAVE) as mock_save:
            client.post("/api/reports/analyze", json={"ticker": "AAPL"})
        mock_save.assert_not_called()

    def test_save_failure_returns_500(self, client, mock_analyze):
        with patch(_SAVE, side_effect=RuntimeError("db write failed")):
            assert client.post("/api/reports/analyze", json={"ticker": "AAPL"}).status_code == 500

    def test_save_failure_detail_is_clean(self, client, mock_analyze):
        with patch(_SAVE, side_effect=RuntimeError("db write failed")):
            data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert data["detail"] == "Failed to save report"

    def test_save_failure_does_not_expose_internal_error(self, client, mock_analyze):
        with patch(_SAVE, side_effect=RuntimeError("some internal db path")):
            data = client.post("/api/reports/analyze", json={"ticker": "AAPL"}).json()
        assert "internal db path" not in data["detail"]


# ---------------------------------------------------------------------------
# GET /api/reports/history
# ---------------------------------------------------------------------------


class TestGetReportHistory:
    def test_returns_200(self, client, mock_list):
        assert client.get("/api/reports/history").status_code == 200

    def test_returns_list(self, client, mock_list):
        assert isinstance(client.get("/api/reports/history").json(), list)

    def test_returns_one_entry(self, client, mock_list):
        assert len(client.get("/api/reports/history").json()) == 1

    def test_entry_has_id(self, client, mock_list):
        assert "id" in client.get("/api/reports/history").json()[0]

    def test_entry_has_ticker(self, client, mock_list):
        assert client.get("/api/reports/history").json()[0]["ticker"] == "AAPL"

    def test_entry_has_score(self, client, mock_list):
        assert client.get("/api/reports/history").json()[0]["score"] == 60.0

    def test_entry_has_category(self, client, mock_list):
        assert client.get("/api/reports/history").json()[0]["category"] == RatingCategory.WATCHLIST.value

    def test_entry_has_confidence(self, client, mock_list):
        assert client.get("/api/reports/history").json()[0]["confidence"] == ConfidenceLevel.MEDIUM.value

    def test_entry_has_created_at(self, client, mock_list):
        assert "created_at" in client.get("/api/reports/history").json()[0]

    def test_entry_has_company_name(self, client, mock_list):
        assert client.get("/api/reports/history").json()[0]["company_name"] == "Apple Inc."

    def test_entry_does_not_have_report(self, client, mock_list):
        assert "report" not in client.get("/api/reports/history").json()[0]

    def test_entry_does_not_have_report_json(self, client, mock_list):
        assert "report_json" not in client.get("/api/reports/history").json()[0]

    def test_calls_list_saved_reports(self, client, mock_list):
        client.get("/api/reports/history")
        mock_list.assert_called_once()

    def test_default_limit_50_passed(self, client, mock_list):
        client.get("/api/reports/history")
        mock_list.assert_called_once_with(limit=50)

    def test_custom_limit_passed(self, client, mock_list):
        client.get("/api/reports/history?limit=10")
        mock_list.assert_called_once_with(limit=10)

    def test_empty_history_returns_empty_list(self, client):
        with patch(_LIST, return_value=[]):
            assert client.get("/api/reports/history").json() == []

    def test_multiple_entries_returned(self, client):
        summaries = [_make_summary(1, "AAPL"), _make_summary(2, "MSFT")]
        with patch(_LIST, return_value=summaries):
            data = client.get("/api/reports/history").json()
        assert len(data) == 2


# ---------------------------------------------------------------------------
# GET /api/reports/{report_id}
# ---------------------------------------------------------------------------


class TestGetSavedReport:
    def test_returns_200_for_existing(self, client, mock_get):
        assert client.get("/api/reports/1").status_code == 200

    def test_returns_404_for_missing(self, client):
        with patch(_GET, return_value=None):
            assert client.get("/api/reports/999").status_code == 404

    def test_404_detail_contains_report_id(self, client):
        with patch(_GET, return_value=None):
            assert "999" in client.get("/api/reports/999").json()["detail"]

    def test_response_has_id(self, client, mock_get):
        assert client.get("/api/reports/1").json()["id"] == 1

    def test_response_has_ticker(self, client, mock_get):
        assert client.get("/api/reports/1").json()["ticker"] == "AAPL"

    def test_response_has_category(self, client, mock_get):
        assert client.get("/api/reports/1").json()["category"] == RatingCategory.WATCHLIST.value

    def test_response_has_score(self, client, mock_get):
        assert client.get("/api/reports/1").json()["score"] == 60.0

    def test_response_has_confidence(self, client, mock_get):
        assert client.get("/api/reports/1").json()["confidence"] == ConfidenceLevel.MEDIUM.value

    def test_response_has_created_at(self, client, mock_get):
        assert "created_at" in client.get("/api/reports/1").json()

    def test_response_has_report(self, client, mock_get):
        assert "report" in client.get("/api/reports/1").json()

    def test_response_report_is_dict(self, client, mock_get):
        assert isinstance(client.get("/api/reports/1").json()["report"], dict)

    def test_response_report_ticker(self, client, mock_get):
        assert client.get("/api/reports/1").json()["report"]["ticker"] == "AAPL"

    def test_calls_get_saved_report_with_correct_id(self, client, mock_get):
        client.get("/api/reports/5")
        mock_get.assert_called_once_with(5)

    def test_non_integer_id_returns_422(self, client):
        assert client.get("/api/reports/abc").status_code == 422


# ---------------------------------------------------------------------------
# Confirm /api/analyze (analysis-only) does not call save
# ---------------------------------------------------------------------------


class TestAnalyzeEndpointDoesNotSave:
    def test_post_analyze_does_not_call_save(self, client):
        with patch(_ANALYZE_STOCK_ANALYSIS, return_value=_make_stock_report()), \
             patch(_SAVE) as mock_save:
            client.post("/api/analyze", json={"ticker": "AAPL"})
        mock_save.assert_not_called()

    def test_post_analyze_does_not_call_list(self, client):
        with patch(_ANALYZE_STOCK_ANALYSIS, return_value=_make_stock_report()), \
             patch(_LIST) as mock_list:
            client.post("/api/analyze", json={"ticker": "AAPL"})
        mock_list.assert_not_called()
