"""
Unit tests for app/services/stock_analysis_service.py.

All data-fetching and pipeline functions are mocked — no network calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.analysis.fundamentals_analysis import FundamentalAnalysisError
from app.analysis.news_analysis import NewsAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
from app.models.stock_report import StockReport
from app.services.stock_analysis_service import (
    _analyze_ticker,
    analyze_stock,
    analyze_watchlist_file,
)
from app.watchlist import WatchlistLoadError, WatchlistResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SVC = "app.services.stock_analysis_service"


def _make_signal(
    category: SignalCategory = SignalCategory.TECHNICAL,
    score_impact: float = 0.10,
) -> Signal:
    return Signal(
        name="Test Signal",
        category=category,
        direction=SignalDirection.BULLISH,
        strength=SignalStrength.MODERATE,
        description="A test signal.",
        score_impact=score_impact,
        confidence=0.65,
    )


def _make_rating(
    ticker: str = "AAPL",
    score: float = 60.0,
    category: RatingCategory = RatingCategory.WATCHLIST,
) -> Rating:
    return Rating(
        ticker=ticker,
        final_category=category,
        score=score,
        confidence=ConfidenceLevel.MEDIUM,
        explanation="Composite rating.",
        technical_score=score,
        data_timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
        data_sources_used=["yfinance"],
        signals_used=[_make_signal()],
    )


def _make_mock_fundamentals(
    beta: float | None = 1.1,
    company_name: str | None = None,
) -> MagicMock:
    m = MagicMock()
    m.beta = beta
    m.company_name = company_name
    return m


def _mock_pipeline(rating: Rating | None = None):
    """Context manager patching the full analysis pipeline at the service level."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=[_make_signal(SignalCategory.NEWS)]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[_make_signal(SignalCategory.FUNDAMENTAL)]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[_make_signal(SignalCategory.RISK)]),
            patch(f"{_SVC}.score_signals",                  return_value=rating or _make_rating()),
        ):
            yield

    return _ctx()


# ---------------------------------------------------------------------------
# analyze_ticker
# ---------------------------------------------------------------------------

class TestAnalyzeTicker:
    def test_returns_rating(self):
        with _mock_pipeline():
            result = _analyze_ticker("AAPL")
        assert isinstance(result, Rating)

    def test_ticker_normalized_to_uppercase(self):
        with _mock_pipeline():
            result = _analyze_ticker("aapl")
        assert result.ticker == "AAPL"

    def test_company_name_attached_from_fundamentals(self):
        fund_mock = _make_mock_fundamentals(company_name="Apple Inc.")
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=fund_mock),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=[]),
            patch(f"{_SVC}.score_signals",                  return_value=_make_rating()),
        ):
            result = _analyze_ticker("AAPL")
        assert result.company_name == "Apple Inc."

    def test_current_price_attached_from_price_data(self):
        price_mock = MagicMock()
        price_mock.__getitem__.return_value.iloc.__getitem__.return_value = 185.50
        with (
            patch(f"{_SVC}.get_price_history",              return_value=price_mock),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=[]),
            patch(f"{_SVC}.score_signals",                  return_value=_make_rating()),
        ):
            result = _analyze_ticker("AAPL")
        assert result.current_price == pytest.approx(185.50)

    def test_passes_beta_to_risk_analysis(self):
        fund_mock = _make_mock_fundamentals(beta=1.5)
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=fund_mock),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]) as mock_risk,
            patch(f"{_SVC}.analyze_news",                   return_value=[]),
            patch(f"{_SVC}.score_signals",                  return_value=_make_rating()),
        ):
            _analyze_ticker("AAPL")
        assert mock_risk.call_args.kwargs.get("beta") == pytest.approx(1.5)

    def test_passes_yfinance_as_data_source(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=[]),
            patch(f"{_SVC}.score_signals",                  return_value=_make_rating()) as mock_score,
        ):
            _analyze_ticker("AAPL")
        assert "yfinance" in mock_score.call_args.kwargs["data_sources_used"]

    def test_news_fetch_failure_is_non_fatal(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                side_effect=Exception("news down")),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=[]),
            patch(f"{_SVC}.score_signals",                  return_value=_make_rating()),
        ):
            result = _analyze_ticker("AAPL")
        assert isinstance(result, Rating)

    def test_news_failure_falls_back_to_empty_analysis(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                side_effect=Exception("timeout")),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=[]) as mock_analyze_news,
            patch(f"{_SVC}.score_signals",                  return_value=_make_rating()),
        ):
            _analyze_ticker("AAPL")
        mock_analyze_news.assert_called_once_with([])

    def test_data_fetch_error_propagates(self):
        with patch(f"{_SVC}.get_price_history", side_effect=DataFetchError("bad ticker")):
            with pytest.raises(DataFetchError):
                _analyze_ticker("INVALID")

    def test_fundamental_fetch_error_propagates(self):
        with (
            patch(f"{_SVC}.get_price_history",        return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals", side_effect=FundamentalDataFetchError("no data")),
        ):
            with pytest.raises(FundamentalDataFetchError):
                _analyze_ticker("AAPL")

    def test_technical_analysis_error_propagates(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", side_effect=TechnicalAnalysisError("bad")),
        ):
            with pytest.raises(TechnicalAnalysisError):
                _analyze_ticker("AAPL")

    def test_scoring_error_propagates(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=[]),
            patch(f"{_SVC}.score_signals",                  side_effect=ScoringError("failed")),
        ):
            with pytest.raises(ScoringError):
                _analyze_ticker("AAPL")

    def test_fundamental_analysis_error_propagates(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      side_effect=FundamentalAnalysisError("bad")),
        ):
            with pytest.raises(FundamentalAnalysisError):
                _analyze_ticker("AAPL")

    def test_risk_analysis_error_propagates(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        side_effect=RiskAnalysisError("bad")),
        ):
            with pytest.raises(RiskAnalysisError):
                _analyze_ticker("AAPL")

    def test_news_analysis_error_propagates(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   side_effect=NewsAnalysisError("bad")),
        ):
            with pytest.raises(NewsAnalysisError):
                _analyze_ticker("AAPL")

    def test_calls_pipeline_in_order(self):
        call_order: list[str] = []
        fund_mock = _make_mock_fundamentals()
        with (
            patch(f"{_SVC}.get_price_history",              side_effect=lambda *a, **kw: call_order.append("fetch") or MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       side_effect=lambda *a, **kw: call_order.append("fetch_fund") or fund_mock),
            patch(f"{_SVC}.get_recent_news",                side_effect=lambda *a, **kw: call_order.append("fetch_news") or []),
            patch(f"{_SVC}.calculate_technical_indicators", side_effect=lambda *a, **kw: call_order.append("calc") or MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    side_effect=lambda *a, **kw: call_order.append("summ") or MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        side_effect=lambda *a, **kw: call_order.append("build_tech") or [_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      side_effect=lambda *a, **kw: call_order.append("build_fund") or []),
            patch(f"{_SVC}.analyze_risk_conditions",        side_effect=lambda *a, **kw: call_order.append("risk") or []),
            patch(f"{_SVC}.analyze_news",                   side_effect=lambda *a, **kw: call_order.append("analyze_news") or []),
            patch(f"{_SVC}.score_signals",                  side_effect=lambda **kw: call_order.append("score") or _make_rating()),
        ):
            _analyze_ticker("AAPL")
        assert call_order == [
            "fetch", "fetch_fund", "fetch_news",
            "calc", "summ",
            "build_tech", "build_fund", "risk", "analyze_news",
            "score",
        ]

    def test_passes_none_beta_when_fundamentals_has_no_beta(self):
        fund_mock = _make_mock_fundamentals(beta=None)
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=fund_mock),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]) as mock_risk,
            patch(f"{_SVC}.analyze_news",                   return_value=[]),
            patch(f"{_SVC}.score_signals",                  return_value=_make_rating()),
        ):
            _analyze_ticker("AAPL")
        assert mock_risk.call_args.kwargs.get("beta") is None

    def test_none_company_name_from_fundamentals_stays_none(self):
        with _mock_pipeline():
            result = _analyze_ticker("AAPL")
        assert result.company_name is None

    def test_news_signals_included_in_score_call(self):
        news_signals = [_make_signal(SignalCategory.NEWS)]
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=news_signals),
            patch(f"{_SVC}.score_signals",                  return_value=_make_rating()) as mock_score,
        ):
            _analyze_ticker("AAPL")
        called_signals = mock_score.call_args.kwargs["signals"]
        assert any(s.category == SignalCategory.NEWS for s in called_signals)


# ---------------------------------------------------------------------------
# analyze_stock
# ---------------------------------------------------------------------------

class TestAnalyzeStock:
    def test_returns_stock_report(self):
        with _mock_pipeline():
            result = analyze_stock("AAPL")
        assert isinstance(result, StockReport)

    def test_stock_report_ticker_matches(self):
        with _mock_pipeline():
            result = analyze_stock("AAPL")
        assert result.ticker == "AAPL"

    def test_stock_report_has_score(self):
        with _mock_pipeline(rating=_make_rating(score=72.5)):
            result = analyze_stock("AAPL")
        assert result.score == pytest.approx(72.5)

    def test_stock_report_has_category(self):
        with _mock_pipeline(rating=_make_rating(category=RatingCategory.BUY_CANDIDATE)):
            result = analyze_stock("AAPL")
        assert result.final_category == RatingCategory.BUY_CANDIDATE

    def test_stock_report_has_confidence(self):
        with _mock_pipeline():
            result = analyze_stock("AAPL")
        assert result.confidence_level == ConfidenceLevel.MEDIUM

    def test_stock_report_has_signals_partitioned(self):
        with _mock_pipeline():
            result = analyze_stock("AAPL")
        # _mock_pipeline provides one signal per category
        assert len(result.technical_signals) > 0 or len(result.fundamental_signals) > 0 \
               or len(result.news_signals) > 0 or len(result.risk_signals) > 0

    def test_delegates_to_analyze_ticker(self):
        with patch(f"{_SVC}._analyze_ticker", return_value=_make_rating()) as mock_ticker:
            result = analyze_stock("AAPL")
        mock_ticker.assert_called_once_with("AAPL")
        assert isinstance(result, StockReport)

    def test_data_fetch_error_propagates(self):
        with patch(f"{_SVC}.get_price_history", side_effect=DataFetchError("bad")):
            with pytest.raises(DataFetchError):
                analyze_stock("INVALID")

    def test_scoring_error_propagates(self):
        with (
            patch(f"{_SVC}.get_price_history",              return_value=MagicMock()),
            patch(f"{_SVC}.get_company_fundamentals",       return_value=_make_mock_fundamentals()),
            patch(f"{_SVC}.get_recent_news",                return_value=[]),
            patch(f"{_SVC}.calculate_technical_indicators", return_value=MagicMock()),
            patch(f"{_SVC}.summarize_technical_signals",    return_value=MagicMock()),
            patch(f"{_SVC}.build_technical_signals",        return_value=[_make_signal()]),
            patch(f"{_SVC}.build_fundamental_signals",      return_value=[]),
            patch(f"{_SVC}.analyze_risk_conditions",        return_value=[]),
            patch(f"{_SVC}.analyze_news",                   return_value=[]),
            patch(f"{_SVC}.score_signals",                  side_effect=ScoringError("failed")),
        ):
            with pytest.raises(ScoringError):
                analyze_stock("AAPL")

    def test_stock_report_is_json_serializable(self):
        with _mock_pipeline():
            result = analyze_stock("AAPL")
        json_str = result.model_dump_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0


# ---------------------------------------------------------------------------
# analyze_watchlist_file
# ---------------------------------------------------------------------------

class TestAnalyzeWatchlistFile:
    def _write_watchlist(self, tmp_path: Path, content: str) -> str:
        p = tmp_path / "watchlist.txt"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_returns_list(self, tmp_path):
        path = self._write_watchlist(tmp_path, "AAPL\n")
        with patch(f"{_SVC}.analyze_stock", return_value=_make_stock_report("AAPL")):
            result = analyze_watchlist_file(path)
        assert isinstance(result, list)

    def test_returns_watchlist_results(self, tmp_path):
        path = self._write_watchlist(tmp_path, "AAPL\n")
        with patch(f"{_SVC}.analyze_stock", return_value=_make_stock_report("AAPL")):
            result = analyze_watchlist_file(path)
        assert all(isinstance(r, WatchlistResult) for r in result)

    def test_single_ticker_produces_one_result(self, tmp_path):
        path = self._write_watchlist(tmp_path, "AAPL\n")
        with patch(f"{_SVC}.analyze_stock", return_value=_make_stock_report("AAPL")):
            result = analyze_watchlist_file(path)
        assert len(result) == 1
        assert result[0].ticker == "AAPL"

    def test_multiple_tickers_produce_multiple_results(self, tmp_path):
        path = self._write_watchlist(tmp_path, "AAPL\nMSFT\n")
        reports = {
            "AAPL": _make_stock_report("AAPL", score=70.0),
            "MSFT": _make_stock_report("MSFT", score=65.0),
        }
        with patch(f"{_SVC}.analyze_stock", side_effect=lambda t: reports[t]):
            result = analyze_watchlist_file(path)
        assert len(result) == 2
        tickers = {r.ticker for r in result}
        assert tickers == {"AAPL", "MSFT"}

    def test_results_sorted_by_score_descending(self, tmp_path):
        path = self._write_watchlist(tmp_path, "LOW\nHIGH\n")
        reports = {
            "LOW":  _make_stock_report("LOW",  score=30.0),
            "HIGH": _make_stock_report("HIGH", score=90.0),
        }
        with patch(f"{_SVC}.analyze_stock", side_effect=lambda t: reports[t]):
            result = analyze_watchlist_file(path)
        assert result[0].ticker == "HIGH"
        assert result[1].ticker == "LOW"

    def test_per_ticker_failure_captured_not_raised(self, tmp_path):
        path = self._write_watchlist(tmp_path, "AAPL\nBAD\n")

        def _fake(ticker: str) -> StockReport:
            if ticker == "BAD":
                raise DataFetchError("no data")
            return _make_stock_report(ticker)

        with patch(f"{_SVC}.analyze_stock", side_effect=_fake):
            result = analyze_watchlist_file(path)
        assert len(result) == 2
        failed = [r for r in result if not r.succeeded]
        assert len(failed) == 1
        assert failed[0].ticker == "BAD"

    def test_failed_result_has_error_message(self, tmp_path):
        path = self._write_watchlist(tmp_path, "BAD\n")
        with patch(f"{_SVC}.analyze_stock", side_effect=DataFetchError("bad ticker")):
            result = analyze_watchlist_file(path)
        assert result[0].error_message is not None
        assert len(result[0].error_message) > 0

    def test_missing_file_raises_watchlist_load_error(self, tmp_path):
        missing = str(tmp_path / "missing.txt")
        with pytest.raises(WatchlistLoadError):
            analyze_watchlist_file(missing)

    def test_empty_file_raises_watchlist_load_error(self, tmp_path):
        path = self._write_watchlist(tmp_path, "")
        with pytest.raises(WatchlistLoadError):
            analyze_watchlist_file(path)

    def test_delegates_to_analyze_stock(self, tmp_path):
        path = self._write_watchlist(tmp_path, "AAPL\n")
        with patch(f"{_SVC}.analyze_stock", return_value=_make_stock_report("AAPL")) as mock_stock:
            analyze_watchlist_file(path)
        mock_stock.assert_called_once_with("AAPL")

    def test_succeeded_result_has_score(self, tmp_path):
        path = self._write_watchlist(tmp_path, "AAPL\n")
        with patch(f"{_SVC}.analyze_stock", return_value=_make_stock_report("AAPL", score=75.0)):
            result = analyze_watchlist_file(path)
        assert result[0].score == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stock_report(
    ticker: str = "AAPL",
    score: float = 60.0,
    category: RatingCategory = RatingCategory.WATCHLIST,
) -> StockReport:
    return StockReport(
        ticker=ticker,
        final_category=category,
        score=score,
        confidence_level=ConfidenceLevel.MEDIUM,
    )
