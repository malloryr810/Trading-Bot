"""
Tests for app/services/report_persistence_service.py.

Uses a temporary SQLite database via the ``engine`` fixture — no writes to the
real project database.  All inputs are built locally; no live API calls.
"""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from app.data.database import build_engine
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport
from app.services.report_persistence_service import (
    get_saved_report,
    list_saved_reports,
    save_stock_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(tmp_path) -> Engine:
    return build_engine(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report(
    ticker: str = "AAPL",
    score: float = 60.0,
    category: RatingCategory = RatingCategory.WATCHLIST,
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    company_name: str | None = "Apple Inc.",
) -> StockReport:
    return StockReport(
        ticker=ticker,
        final_category=category,
        score=score,
        confidence_level=confidence,
        company_name=company_name,
    )


# ---------------------------------------------------------------------------
# save_stock_report
# ---------------------------------------------------------------------------


class TestSaveStockReport:
    def test_returns_dict(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert isinstance(result, dict)

    def test_id_is_integer(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert isinstance(result["id"], int)

    def test_id_is_positive(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert result["id"] > 0

    def test_sequential_ids(self, engine):
        r1 = save_stock_report(_make_report("AAPL"), engine=engine)
        r2 = save_stock_report(_make_report("MSFT"), engine=engine)
        assert r2["id"] == r1["id"] + 1

    def test_ticker_matches(self, engine):
        result = save_stock_report(_make_report("MSFT"), engine=engine)
        assert result["ticker"] == "MSFT"

    def test_ticker_is_normalized_uppercase(self, engine):
        report = _make_report("aapl")
        # StockReport normalizes ticker to uppercase via field_validator
        result = save_stock_report(report, engine=engine)
        assert result["ticker"] == "AAPL"

    def test_category_is_string(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert isinstance(result["category"], str)

    def test_category_value(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert result["category"] == RatingCategory.WATCHLIST.value

    def test_score_value(self, engine):
        result = save_stock_report(_make_report(score=75.5), engine=engine)
        assert result["score"] == 75.5

    def test_confidence_is_string(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert isinstance(result["confidence"], str)

    def test_confidence_value(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert result["confidence"] == ConfidenceLevel.MEDIUM.value

    def test_company_name_saved(self, engine):
        result = save_stock_report(_make_report(company_name="Apple Inc."), engine=engine)
        assert result["company_name"] == "Apple Inc."

    def test_company_name_none_saved(self, engine):
        result = save_stock_report(_make_report(company_name=None), engine=engine)
        assert result["company_name"] is None

    def test_created_at_present(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert result["created_at"] is not None

    def test_report_key_present(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert "report" in result

    def test_report_is_dict(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert isinstance(result["report"], dict)

    def test_report_ticker_matches(self, engine):
        result = save_stock_report(_make_report("NVDA"), engine=engine)
        assert result["report"]["ticker"] == "NVDA"

    def test_report_score_matches(self, engine):
        result = save_stock_report(_make_report(score=80.0), engine=engine)
        assert result["report"]["score"] == 80.0

    def test_report_category_matches(self, engine):
        result = save_stock_report(
            _make_report(category=RatingCategory.BUY_CANDIDATE), engine=engine
        )
        assert result["report"]["final_category"] == RatingCategory.BUY_CANDIDATE.value

    def test_no_report_json_key_in_result(self, engine):
        result = save_stock_report(_make_report(), engine=engine)
        assert "report_json" not in result

    def test_multiple_saves_return_distinct_ids(self, engine):
        ids = {save_stock_report(_make_report(), engine=engine)["id"] for _ in range(3)}
        assert len(ids) == 3


# ---------------------------------------------------------------------------
# list_saved_reports
# ---------------------------------------------------------------------------


class TestListSavedReports:
    def test_returns_list(self, engine):
        assert isinstance(list_saved_reports(engine=engine), list)

    def test_empty_when_no_reports(self, engine):
        assert list_saved_reports(engine=engine) == []

    def test_returns_one_after_save(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert len(list_saved_reports(engine=engine)) == 1

    def test_returns_all_saved(self, engine):
        save_stock_report(_make_report("AAPL"), engine=engine)
        save_stock_report(_make_report("MSFT"), engine=engine)
        assert len(list_saved_reports(engine=engine)) == 2

    def test_ordered_newest_first_by_id(self, engine):
        s1 = save_stock_report(_make_report("AAPL"), engine=engine)
        s2 = save_stock_report(_make_report("MSFT"), engine=engine)
        results = list_saved_reports(engine=engine)
        assert results[0]["id"] == s2["id"]
        assert results[1]["id"] == s1["id"]

    def test_summary_has_id(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert "id" in list_saved_reports(engine=engine)[0]

    def test_summary_has_ticker(self, engine):
        save_stock_report(_make_report("GOOGL"), engine=engine)
        assert list_saved_reports(engine=engine)[0]["ticker"] == "GOOGL"

    def test_summary_has_company_name(self, engine):
        save_stock_report(_make_report(company_name="Google LLC"), engine=engine)
        assert list_saved_reports(engine=engine)[0]["company_name"] == "Google LLC"

    def test_summary_has_score(self, engine):
        save_stock_report(_make_report(score=55.0), engine=engine)
        assert list_saved_reports(engine=engine)[0]["score"] == 55.0

    def test_summary_has_category(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert list_saved_reports(engine=engine)[0]["category"] == RatingCategory.WATCHLIST.value

    def test_summary_has_confidence(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert list_saved_reports(engine=engine)[0]["confidence"] == ConfidenceLevel.MEDIUM.value

    def test_summary_has_created_at(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert "created_at" in list_saved_reports(engine=engine)[0]

    def test_summary_does_not_contain_report_json(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert "report_json" not in list_saved_reports(engine=engine)[0]

    def test_summary_does_not_contain_report(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert "report" not in list_saved_reports(engine=engine)[0]

    def test_limit_applied(self, engine):
        for _ in range(5):
            save_stock_report(_make_report(), engine=engine)
        assert len(list_saved_reports(limit=3, engine=engine)) == 3

    def test_default_limit_of_50(self, engine):
        for _ in range(55):
            save_stock_report(_make_report(), engine=engine)
        assert len(list_saved_reports(engine=engine)) == 50

    def test_limit_1_returns_newest(self, engine):
        save_stock_report(_make_report("AAPL"), engine=engine)
        s2 = save_stock_report(_make_report("MSFT"), engine=engine)
        result = list_saved_reports(limit=1, engine=engine)
        assert len(result) == 1
        assert result[0]["id"] == s2["id"]


# ---------------------------------------------------------------------------
# get_saved_report
# ---------------------------------------------------------------------------


class TestGetSavedReport:
    def test_returns_none_for_missing_id(self, engine):
        assert get_saved_report(999, engine=engine) is None

    def test_returns_none_for_zero_id(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert get_saved_report(0, engine=engine) is None

    def test_returns_dict_for_existing(self, engine):
        saved = save_stock_report(_make_report(), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert isinstance(result, dict)

    def test_id_matches(self, engine):
        saved = save_stock_report(_make_report(), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert result["id"] == saved["id"]

    def test_ticker_matches(self, engine):
        saved = save_stock_report(_make_report("GOOGL"), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert result["ticker"] == "GOOGL"

    def test_category_matches(self, engine):
        saved = save_stock_report(
            _make_report(category=RatingCategory.AVOID), engine=engine
        )
        result = get_saved_report(saved["id"], engine=engine)
        assert result["category"] == RatingCategory.AVOID.value

    def test_score_matches(self, engine):
        saved = save_stock_report(_make_report(score=42.0), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert result["score"] == 42.0

    def test_confidence_matches(self, engine):
        saved = save_stock_report(
            _make_report(confidence=ConfidenceLevel.HIGH), engine=engine
        )
        result = get_saved_report(saved["id"], engine=engine)
        assert result["confidence"] == ConfidenceLevel.HIGH.value

    def test_company_name_matches(self, engine):
        saved = save_stock_report(_make_report(company_name="Acme Corp"), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert result["company_name"] == "Acme Corp"

    def test_report_key_present(self, engine):
        saved = save_stock_report(_make_report(), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert "report" in result

    def test_report_is_dict(self, engine):
        saved = save_stock_report(_make_report(), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert isinstance(result["report"], dict)

    def test_report_ticker_roundtrips(self, engine):
        save_stock_report(_make_report("AMZN"), engine=engine)
        summary = list_saved_reports(engine=engine)[0]
        result = get_saved_report(summary["id"], engine=engine)
        assert result["report"]["ticker"] == "AMZN"

    def test_report_score_roundtrips(self, engine):
        saved = save_stock_report(_make_report(score=67.5), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert result["report"]["score"] == 67.5

    def test_report_category_roundtrips(self, engine):
        saved = save_stock_report(
            _make_report(category=RatingCategory.BUY_CANDIDATE), engine=engine
        )
        result = get_saved_report(saved["id"], engine=engine)
        assert result["report"]["final_category"] == RatingCategory.BUY_CANDIDATE.value

    def test_report_confidence_roundtrips(self, engine):
        saved = save_stock_report(
            _make_report(confidence=ConfidenceLevel.LOW), engine=engine
        )
        result = get_saved_report(saved["id"], engine=engine)
        assert result["report"]["confidence_level"] == ConfidenceLevel.LOW.value

    def test_no_report_json_key_in_result(self, engine):
        saved = save_stock_report(_make_report(), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert "report_json" not in result

    def test_two_reports_retrievable_independently(self, engine):
        s1 = save_stock_report(_make_report("AAPL"), engine=engine)
        s2 = save_stock_report(_make_report("MSFT"), engine=engine)
        r1 = get_saved_report(s1["id"], engine=engine)
        r2 = get_saved_report(s2["id"], engine=engine)
        assert r1["ticker"] == "AAPL"
        assert r2["ticker"] == "MSFT"

    def test_returns_none_for_negative_id(self, engine):
        save_stock_report(_make_report(), engine=engine)
        assert get_saved_report(-1, engine=engine) is None


# ---------------------------------------------------------------------------
# created_at timezone normalization
# ---------------------------------------------------------------------------


class TestCreatedAtTimezone:
    """Verify datetimes read back from SQLite are always UTC-aware.

    SQLite drops timezone info on storage; the persistence service must
    re-attach UTC so that all API responses use a consistent representation.
    """

    def test_list_created_at_is_timezone_aware(self, engine):
        save_stock_report(_make_report(), engine=engine)
        result = list_saved_reports(engine=engine)[0]
        assert result["created_at"].tzinfo is not None

    def test_list_created_at_is_utc(self, engine):
        from datetime import timezone as tz
        save_stock_report(_make_report(), engine=engine)
        result = list_saved_reports(engine=engine)[0]
        assert result["created_at"].utcoffset().total_seconds() == 0

    def test_get_created_at_is_timezone_aware(self, engine):
        saved = save_stock_report(_make_report(), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert result["created_at"].tzinfo is not None

    def test_get_created_at_is_utc(self, engine):
        saved = save_stock_report(_make_report(), engine=engine)
        result = get_saved_report(saved["id"], engine=engine)
        assert result["created_at"].utcoffset().total_seconds() == 0

    def test_save_and_list_created_at_agree(self, engine):
        """save returns UTC-aware; list must return the same moment."""
        saved = save_stock_report(_make_report(), engine=engine)
        listed = list_saved_reports(engine=engine)[0]
        # Compare as UTC timestamps; microsecond precision is acceptable
        assert saved["created_at"].utctimetuple() == listed["created_at"].utctimetuple()
