"""
Tests for /api/discovery* endpoints.

Integration tests over the real routes and the real discovery service. The two
external touch points — the stage-1 pre-screen and the analysis pipeline — are
patched inside the discovery service, so no test performs a network call.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.data.universe_loader import STARTER_LARGE_CAP, load_universe
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.services.discovery_screening import PrescreenResult

_ANALYZE = "app.services.discovery_service.analyze_stock_rating"
_PRESCREEN = "app.services.discovery_service.prescreen_ticker"

UNIVERSE_TICKERS = [entry.ticker for entry in load_universe(STARTER_LARGE_CAP)]


def _rating(ticker: str, score: float = 60.0) -> Rating:
    return Rating(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=score,
        confidence=ConfidenceLevel.MEDIUM,
        explanation=f"Rating for {ticker}.",
        technical_score=55.0,
        fundamental_score=52.0,
        news_score=50.0,
        risk_score=58.0,
        company_name=f"{ticker} Inc.",
        current_price=123.45,
        data_sources_used=["yfinance"],
    )


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture()
def stubbed_pipeline():
    """Patch the pre-screen and analysis pipeline used by the discovery service."""
    with patch(_PRESCREEN, side_effect=lambda t: PrescreenResult(t, True)) as prescreen:
        with patch(_ANALYZE, side_effect=_rating) as analyze:
            yield prescreen, analyze


# ---------------------------------------------------------------------------
# GET /api/discovery/modes and /universes
# ---------------------------------------------------------------------------


class TestMetadataRoutes:
    def test_modes_returns_200(self, client):
        assert client.get("/api/discovery/modes").status_code == 200

    def test_modes_lists_every_supported_mode(self, client):
        keys = {item["key"] for item in client.get("/api/discovery/modes").json()}
        assert keys == {"overall", "momentum", "quality", "value", "defensive", "avoid"}

    def test_modes_describe_their_ranking(self, client):
        for item in client.get("/api/discovery/modes").json():
            assert item["label"]
            assert item["description"]
            assert item["ranking"]

    def test_universes_returns_200(self, client):
        assert client.get("/api/discovery/universes").status_code == 200

    def test_universes_includes_the_starter_universe(self, client):
        body = client.get("/api/discovery/universes").json()
        starter = next(item for item in body if item["key"] == STARTER_LARGE_CAP)
        assert starter["size"] == len(UNIVERSE_TICKERS)


# ---------------------------------------------------------------------------
# GET /api/discovery — success
# ---------------------------------------------------------------------------


class TestDiscoveryRoute:
    def test_returns_200(self, client, stubbed_pipeline):
        response = client.get("/api/discovery", params={"limit": 3, "max_full_analysis": 3})
        assert response.status_code == 200

    def test_returns_the_requested_number_of_results(self, client, stubbed_pipeline):
        body = client.get(
            "/api/discovery", params={"limit": 2, "max_full_analysis": 4}
        ).json()
        assert len(body["results"]) == 2

    def test_response_includes_run_metadata(self, client, stubbed_pipeline):
        body = client.get(
            "/api/discovery", params={"limit": 2, "max_full_analysis": 2}
        ).json()
        for field in (
            "mode",
            "universe",
            "universe_name",
            "limit",
            "max_full_analysis",
            "universe_size",
            "results",
            "warnings",
            "started_at",
            "completed_at",
            "data_sources_used",
        ):
            assert field in body

    def test_candidate_shape(self, client, stubbed_pipeline):
        body = client.get(
            "/api/discovery", params={"limit": 1, "max_full_analysis": 1}
        ).json()
        candidate = body["results"][0]
        for field in (
            "ticker",
            "company_name",
            "sector",
            "industry",
            "mode",
            "rank",
            "match_reason",
            "final_category",
            "score",
            "confidence_level",
            "current_price",
            "technical_score",
            "key_positive_factors",
            "key_risks",
            "data_sources_used",
        ):
            assert field in candidate

    def test_defaults_apply_without_query_parameters(self, client, stubbed_pipeline):
        body = client.get("/api/discovery").json()
        assert body["mode"] == "overall"
        assert body["universe"] == STARTER_LARGE_CAP
        assert body["limit"] == 10
        assert body["max_full_analysis"] == 25

    def test_mode_is_applied(self, client, stubbed_pipeline):
        body = client.get(
            "/api/discovery",
            params={"mode": "momentum", "limit": 2, "max_full_analysis": 2},
        ).json()
        assert body["mode"] == "momentum"
        assert all(c["mode"] == "momentum" for c in body["results"])

    def test_full_analysis_is_bounded_by_max_full_analysis(self, client, stubbed_pipeline):
        _, analyze = stubbed_pipeline
        client.get("/api/discovery", params={"limit": 2, "max_full_analysis": 2})
        assert analyze.call_count == 2


# ---------------------------------------------------------------------------
# GET /api/discovery — partial and total failure
# ---------------------------------------------------------------------------


class TestDiscoveryFailureHandling:
    def test_partial_failure_still_returns_200(self, client):
        def _analyze(ticker: str) -> Rating:
            if ticker == UNIVERSE_TICKERS[0]:
                raise RuntimeError("no data for this ticker")
            return _rating(ticker)

        with patch(_PRESCREEN, side_effect=lambda t: PrescreenResult(t, True)):
            with patch(_ANALYZE, side_effect=_analyze):
                response = client.get(
                    "/api/discovery", params={"limit": 3, "max_full_analysis": 3}
                )
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 2
        assert body["warnings"][0]["stage"] == "analysis"

    def test_no_candidates_returns_200_with_warnings(self, client):
        with patch(
            _PRESCREEN, side_effect=lambda t: PrescreenResult(t, False, "no history")
        ):
            with patch(_ANALYZE) as analyze:
                response = client.get(
                    "/api/discovery", params={"limit": 3, "max_full_analysis": 3}
                )
        assert response.status_code == 200
        body = response.json()
        assert body["results"] == []
        assert len(body["warnings"]) == len(UNIVERSE_TICKERS)
        analyze.assert_not_called()

    def test_unexpected_service_failure_returns_500(self, client):
        with patch(
            "app.api.routes.discovery.run_discovery", side_effect=RuntimeError("boom")
        ):
            assert client.get("/api/discovery").status_code == 500


# ---------------------------------------------------------------------------
# GET /api/discovery — validation
# ---------------------------------------------------------------------------


class TestDiscoveryValidation:
    def test_unknown_mode_returns_400(self, client, stubbed_pipeline):
        assert client.get("/api/discovery", params={"mode": "moonshot"}).status_code == 400

    def test_unknown_universe_returns_400(self, client, stubbed_pipeline):
        assert client.get("/api/discovery", params={"universe": "sp500"}).status_code == 400

    def test_zero_limit_returns_400(self, client, stubbed_pipeline):
        assert client.get("/api/discovery", params={"limit": 0}).status_code == 400

    def test_oversized_limit_returns_400(self, client, stubbed_pipeline):
        assert client.get("/api/discovery", params={"limit": 500}).status_code == 400

    def test_zero_max_full_analysis_returns_400(self, client, stubbed_pipeline):
        params = {"max_full_analysis": 0}
        assert client.get("/api/discovery", params=params).status_code == 400

    def test_oversized_max_full_analysis_returns_400(self, client, stubbed_pipeline):
        params = {"max_full_analysis": 500}
        assert client.get("/api/discovery", params=params).status_code == 400

    def test_limit_above_max_full_analysis_returns_400(self, client, stubbed_pipeline):
        params = {"limit": 20, "max_full_analysis": 5}
        assert client.get("/api/discovery", params=params).status_code == 400

    def test_validation_failure_runs_no_analysis(self, client, stubbed_pipeline):
        _, analyze = stubbed_pipeline
        client.get("/api/discovery", params={"mode": "nonsense"})
        analyze.assert_not_called()

    def test_non_numeric_limit_returns_422(self, client, stubbed_pipeline):
        # FastAPI rejects a non-integer query value before the service is reached.
        assert client.get("/api/discovery", params={"limit": "ten"}).status_code == 422

    def test_error_body_explains_the_problem(self, client, stubbed_pipeline):
        detail = client.get("/api/discovery", params={"mode": "moonshot"}).json()["detail"]
        assert "moonshot" in detail
