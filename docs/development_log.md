# Development Log

## 2026-05-24 — Local storage layer

- Replaced docstring-only stub with full implementation of `app/data/storage.py`
- `StorageError` — single exception class for all storage failures
- `build_report_filename(ticker, timestamp=None, extension="txt") -> str` — deterministic `TICKER_YYYYMMDD_HHMMSS.ext` filenames; validates ticker and extension; supports `"txt"`, `".txt"`, `"json"`, `".json"`
- `ensure_output_dir(output_dir) -> Path` — creates directory tree with `parents=True, exist_ok=True`; wraps `OSError` in `StorageError`
- `save_text_report(report_text, ticker, output_dir="outputs/reports", timestamp=None) -> Path` — validates non-blank text, calls `ensure_output_dir`, writes UTF-8
- `save_json_result(result, ticker, output_dir="outputs/results", timestamp=None) -> Path` — accepts plain `Mapping` or Pydantic `BaseModel`; uses `model_dump(mode="json")` for models; `json.dumps` with `indent=2, sort_keys=True`; `_json_default` fallback handles `datetime` objects
- Added 77 tests in `tests/test_storage.py`; all use `tmp_path` — no writes to real project directories
- Not wired into CLI yet; that is the recommended next step

## 2026-05-24 — Wire news analysis into pipeline

- Updated `_WEIGHTS` in `scoring.py`: Technical 35%, Fundamental 25%, **News 25%**, Risk 15% (sum 1.00; re-normalised when a category is absent)
- `score_signals()` now handles `SignalCategory.NEWS`: computes `news_score`, populates `news_summary`, includes news signal count in `explanation`, passes `news_score` and `news_summary` to `Rating`
- Error message updated: "Expected at least one TECHNICAL, FUNDAMENTAL, NEWS, or RISK signal."
- `main.py`: added `get_recent_news` and `analyze_news` imports; `analyze_ticker()` now fetches news (non-fatal — falls back to `analyze_news([])` on any exception), calls `analyze_news(news_items)`, and includes `news_signals` in the `score_signals()` call
- `tests/test_composite_scoring.py`: renamed `test_only_news_signals_raises` → `test_only_news_signals_does_not_raise`; replaced `TestUnsupportedCategoriesIgnored` with `TestNewsSignals` (10 tests); added `test_news_only_weight_is_100pct` to `TestRenormalisation`; added `TestFourWayWeighting` (4 tests)
- `tests/test_main.py`: added `_FETCH_NEWS` and `_ANALYZE_NEWS` patch targets; updated `_mock_pipeline`; updated `test_calls_pipeline_in_order` with new step order; added news patches to two individual beta tests; added `TestNewsFetchInPipeline` (3 tests)
- No changes to `app/models/rating.py` or `app/reports/stock_report.py` — both already handled `news_score` and `news_summary`
- Full suite 687/687 passing

## 2026-05-24 — News analysis and data layers

- Implemented `app/models/news.py` with `NewsItem` Pydantic model; required `title` (validated non-blank), optional `publisher`, `link`, `published_at`, `summary`, `related_tickers: list[str]`
- Implemented `app/data/news_data.py` with `get_recent_news(ticker, limit=10) -> list[NewsItem]` and `NewsFetchError`; handles both flat and nested-content yfinance response shapes; converts Unix timestamps to timezone-aware UTC datetimes; limit validated to reject bool, float, and zero/negative integers
- Implemented `app/analysis/news_analysis.py` with `analyze_news(news_items) -> list[Signal]` and `NewsAnalysisError`; always returns exactly 3 `SignalCategory.NEWS` signals (Sentiment, Risk Headlines, Coverage); rule-based keyword matching using frozensets; empty input produces 3 neutral no-data signals (confidence=0.30); score impacts capped at ±0.20; coverage signal always score_impact=0.0
- Added 63 tests in `tests/test_news_data.py` and 95 tests in `tests/test_news_analysis.py`; all mocked — no live API calls

## 2026-05-23 — Architecture review and cleanup

Code-quality review after integrating three analysis branches. No behavior changes.

- **`app/analysis/technicals.py`**: renamed private `_maybe_float` → `_safe_float` for
  consistency with `risk_analysis.py` and `fundamentals.py`; replaced `f != f` NaN-only
  check with `math.isfinite()` which also filters Inf; added `import math`
- **`app/analysis/scoring.py`**: updated `score_signals` docstring (weight values were
  still 60/40 from before risk was wired in); updated `score_technical_signals` docstring
  and `explanation` string (both said "not implemented yet" when they are now implemented)
- **`app/reports/stock_report.py`**: removed spurious double blank line left by linter
- No structural changes, no new abstractions, no new dependencies

Issues noted but intentionally left alone:
- `_validate_ticker` is duplicated between `market_data.py` and `fundamentals.py` — they
  raise different exceptions by design; extracting to shared utils would create
  cross-layer coupling for trivial gain
- `_safe_float` is duplicated between `risk_analysis.py` and `fundamentals.py` — same
  reason; private helpers in independent modules
- `_score_breakdown` shows "(not scored)" for any sub-score of 0.0 — borderline issue
  only for the rare case where a scored category lands exactly at 0.0; acceptable now
- `format_rating_output` in `main.py` is not on the live code path but is intentionally
  retained and tested as an alternate/simpler formatter

## 2026-05-23 — Wire risk analysis into pipeline

- Updated `_WEIGHTS` in `scoring.py`: Technical 35%, Fundamental 25%, Risk 15% (total 0.75, re-normalised when a category is absent)
- `score_signals()` now handles `SignalCategory.RISK`: computes `risk_score`, populates `risk_summary`, includes risk signal count in `explanation`, passes `risk_score` and `risk_summary` to `Rating`
- Error message updated: "Expected at least one TECHNICAL, FUNDAMENTAL, or RISK signal."
- `stock_report.py`: RISK CONDITIONS section always rendered; fallback text "Risk conditions were not assessed for this report." shown when `risk_summary` is None
- `main.py`: full pipeline wired — fetches fundamentals, builds all three signal sets, scores with `score_signals()`; handles `FundamentalDataFetchError`, `FundamentalAnalysisError`, and `RiskAnalysisError` in `main()`
- Updated `tests/test_composite_scoring.py`: fixed 7 tests that assumed old 60/40 weights; added `TestRiskSignals` (7 tests) and `TestThreeWayWeighting` (4 tests); renamed two `TestNoSupportedCategories` tests that no longer raise
- Updated `tests/test_main.py`: rewrote mock targets for new pipeline; added tests for `FundamentalDataFetchError`, `FundamentalAnalysisError`, `RiskAnalysisError`; added `test_passes_beta_from_fundamentals_to_risk` and `test_passes_none_beta_when_fundamentals_has_no_beta`
- Added 3 tests to `tests/test_stock_report.py` for the RISK CONDITIONS section
- Full suite 515/515 passing

## 2026-05-23 — Risk analysis module

- Implemented `app/analysis/risk_analysis.py` with `analyze_risk_conditions()` and `RiskAnalysisError`
- Produces 4 signals (or 5 when `beta` is provided), all using `SignalCategory.RISK`
- **Volatility Risk**: annualized std of daily returns; bearish >= 45%, bullish < 25%
- **Maximum Drawdown Risk**: peak-to-trough decline; bearish <= -35%, neutral -35% to -15%, bullish > -15%
- **Recent Trend Risk**: 30-trading-day price return; bearish <= -10%, bullish >= 5%; neutral signal with low confidence when fewer than 31 rows are available
- **Liquidity Risk**: average daily volume; bearish < 500k, neutral 500k–1M, bullish >= 1M; graceful neutral when volume is all NaN
- **Beta Risk** (optional): bearish >= 1.5, neutral 0.8–1.5, bullish < 0.8; raises `RiskAnalysisError` for NaN/Inf beta
- Input validation follows the same pattern as `technicals.py` and `fundamentals_analysis.py`
- `_insufficient_data_signal()` helper consolidates the neutral/low-confidence pattern for missing data
- `_safe_float()` converts NaN/Inf safely to None for all calculations
- Input DataFrame is never mutated (`.dropna()` returns a new Series)
- Added 72 unit tests in `tests/test_risk_analysis.py`; full suite 496/496 passing
- Not yet wired into `scoring.py`, `main.py`, or `stock_report.py`

## 2026-05-23 — Plain-text stock report generator

- Added `app/reports/stock_report.py` with `generate_stock_report()` and `StockReportError`
- Report is a single formatted string with eight sections: header, recommendation, score
  breakdown, analysis summaries (technical/fundamental/news/risk when present), signals
  table, key strengths, key risks, triggers, and disclaimer
- Each signal rendered with a direction indicator (`[+]`/`[-]`/`[ ]`), direction, strength, name, and description
- Optional params: `company_name`, `current_price`, `data_sources` (falls back to `rating.data_sources_used`)
- Input validated with `StockReportError` for bad ticker, non-Rating, or non-Signal items
- `app/main.py` updated to call `generate_stock_report` instead of the old `format_rating_output`
- `format_rating_output` retained in `main.py` (tested independently in `test_main.py`)
- Added 67 unit tests in `tests/test_stock_report.py`; full suite 427/427 passing

## 2026-05-19 — Composite scoring

- Added `score_signals()` to `app/analysis/scoring.py` alongside existing `score_technical_signals()`
- Weights: Technical 60%, Fundamental 40%; re-normalised to 100% when a category is absent
- Unsupported categories (NEWS, RISK) are silently ignored; raises `ScoringError` only if no supported categories are present at all
- Added `_WEIGHTS` constant, `_signals_to_score()` shared formula helper, and `_validate_composite_inputs()`
- `score_technical_signals()` unchanged; its internal validator refactored to be standalone
- `fundamental_summary` populated when fundamental signals are present; `technical_summary` likewise
- Added 58 unit tests in `tests/test_composite_scoring.py`; full suite 360/360 passing

## 2026-05-17 — Fundamentals analysis layer

- Implemented `app/analysis/fundamentals_analysis.py` with `build_fundamental_signals()` and `FundamentalAnalysisError`
- Produces 5 typed FUNDAMENTAL Signals: Valuation, Profitability, Growth, Debt Levels, Free Cash Flow
- Valuation: uses forward P/E (preferred) or trailing P/E; thresholds at 0/5/25/40; BEARISH for negative or >40 PE
- Profitability: profit_margin thresholds at 0/5%/15%; BULLISH STRONG at >=15%, BEARISH below 0
- Growth: both revenue_growth and earnings_growth assessed together; 4 outcomes (strong/positive/mixed/declining) plus partial and missing
- Debt: debt_to_equity thresholds at 50/150; negative D/E treated as unusual with lower confidence
- Cash flow: positive FCF is BULLISH, negative is BEARISH, zero is NEUTRAL
- Missing fields always produce a neutral Signal with confidence=0.30 rather than raising exceptions
- Also removed unused `Field` import from `app/models/fundamentals.py` (Pylance diagnostic)
- Added 65 unit tests in `tests/test_fundamentals_analysis.py`; full suite 302/302 passing
- Scoring and CLI untouched; fundamental signals not yet wired into scoring

## 2026-05-17 — Fundamental data layer

- Added `app/models/fundamentals.py` with `CompanyFundamentals` Pydantic model
- Added `app/data/fundamentals.py` with `get_company_fundamentals()` and `FundamentalDataFetchError`
- Fetches 15 fields from `yfinance.Ticker.info`: identity (name, sector, industry) and key metrics (market cap, P/E ratios, P/B, margins, growth rates, D/E, FCF, dividend yield, beta)
- `_safe_float` converts yfinance values safely: rejects None, NaN, Inf, and non-numeric strings → None
- `_extract_company_name` prefers `longName` over `shortName`; raises if neither is present
- Added 43 unit tests in `tests/test_fundamentals_data.py`; full suite 237/237 passing
- Scoring and technical analysis untouched; scoring weights unchanged

## 2026-05-14 — v0.1 milestone quality review

- Reviewed all 7 source modules, 7 test files, README, CLAUDE.md, and 4 docs files
- No architectural violations, no import boundary issues, no stale or live-API tests found
- Removed `# type: ignore[union-attr]` in `_validate_summary_input` — converted to `set(summary)` for clean narrowing
- Fixed `rating.py` module docstring: "future scoring engine" → "scoring engine"
- Updated README: corrected stale test count (41→194), placeholder labels on `main.py` and `models/`
- Updated CLAUDE.md: added all 6 currently-implemented modules to the table; added `<TICKER>` to CLI example
- Updated `docs/architecture.md`: marked each file as ✓ implemented or ○ planned
- Updated `docs/scoring_rules.md`: replaced placeholder thresholds with the actual implemented values; moved risk_block note to "planned" section
- 194/194 tests passing; `python -m app.main AAPL` produces correct technical-only output

## 2026-05-14 — CLI pipeline wired in app/main.py

- Implemented `analyze_ticker(ticker)` — orchestrates the full technical analysis pipeline
- Implemented `format_rating_output(rating)` — renders a human-readable terminal summary
- Implemented `main(argv)` — CLI entry point; handles missing ticker (exit 1 + usage), `DataFetchError`, `TechnicalAnalysisError`, and `ScoringError` gracefully (stderr + exit 1)
- Added 24 unit tests in `tests/test_main.py`; entire pipeline mocked — no live API calls
- Full suite 194/194 passing; smoke test `python -m app.main AAPL` produces structured output

## 2026-05-14 — Technical-only scoring module

- Added `app/analysis/scoring.py` with `ScoringError` and `score_technical_signals()`
- Scoring: sums `score_impact` across signals, clamps to [-1, 1], scales to 0–100 via `50 + impact * 50`
- Maps composite score to `RatingCategory`; maps average signal confidence to `ConfidenceLevel`
- Populates `key_positive_factors` from bullish signals and `key_risks` from bearish signals
- Non-implemented sub-scores (`fundamental_score`, `news_score`, `risk_score`) explicitly set to 0.0
- Added 36 unit tests in `tests/test_scoring.py`; full suite 170/170 passing

## 2026-05-14 — Typed Rating model foundation

- Added `app/models/rating.py` with `RatingCategory` and `ConfidenceLevel` enums and `Rating` Pydantic model
- `RatingCategory` uses project-specific labels: Strong Buy Candidate, Buy Candidate, Watchlist, Hold, Avoid, Sell / Exit Warning
- Score fields (composite + 4 sub-scores) constrained to 0–100 via `Field(ge=0.0, le=100.0)`
- Ticker stripped and uppercased via `@field_validator`; explanation validated non-blank
- `signals_used: list[Signal]` embeds provenance directly in the output model
- Added `is_positive_rating`, `is_negative_rating`, `is_neutral_rating` convenience properties
- Added 37 unit tests in `tests/test_rating.py` including JSON round-trip; full suite 134/134 passing

## 2026-05-14 — Technical signal builder

- Added `build_technical_signals(indicator_summary)` to `app/analysis/technicals.py`
- Converts the dict from `summarize_technical_signals()` into 7 typed `Signal` objects (trend, RSI, MACD, price vs SMA 20/50/200, volume)
- Added `REQUIRED_SUMMARY_KEYS` constant and `_validate_summary_input` helper
- Added 34 unit tests in `tests/test_build_technical_signals.py`; full suite 97/97 passing

## 2026-05-14 — Typed signal model foundation

- Added `app/models/signal.py` with `Signal` Pydantic model and `SignalCategory`, `SignalDirection`, `SignalStrength` enums
- Validated: name/description non-blank, `score_impact` ∈ [-1.0, 1.0], `confidence` ∈ [0.0, 1.0]
- Optional fields: `value`, `source`, `timestamp`, `metadata` (safe default factory)
- Added `is_bullish`, `is_bearish`, `is_neutral` convenience properties
- Added 22 unit tests in `tests/test_signal.py`; full suite 63/63 passing

## 2026-05-14 — Documentation update and foundation review

- README rewritten to accurately reflect implemented state; removed references to unbuilt features
- CLAUDE.md updated with explicit guardrails, implemented module list, layer rules, and development standards
- `app/analysis/technicals.py`: removed redundant `isinstance` check in `_validate_ohlcv_input` and dropped unnecessary `# type: ignore` comment
- `app/analysis/technicals.py`: fixed `_calculate_rsi` to use `.where()` instead of `.fillna(100)` so pre-window rows correctly stay NaN rather than being incorrectly filled with 100
- All 41 tests pass; no behavior changes

## 2026-05-14 — Technical analysis module implemented

- Added `app/analysis/technicals.py` with `TechnicalAnalysisError`, `calculate_technical_indicators()`, and `summarize_technical_signals()`
- Indicators: SMA 20/50/200, RSI 14, MACD/signal/histogram, volume SMA 20, daily return
- Summary helper classifies trend (bullish/bearish/mixed), RSI condition, and MACD condition from the latest row
- All calculations use pandas only; no external indicator libraries
- Added 26 unit tests in `tests/test_technicals.py` (no network calls); full suite 41/41 passing

## 2026-05-12 — Market data module implemented

- Added `app/data/market_data.py` with `get_price_history()` and `DataFetchError`
- Fetches historical OHLCV data via yfinance; normalizes column names; validates inputs and output shape
- Added 15 unit tests in `tests/test_market_data.py` (all passing, no live API calls)

## 2026-05-12 — Project skeleton created

- Initialized repository with full modular project structure
- Created `app/` package with `data/`, `analysis/`, `reports/`, `models/`, and `utils/` sub-packages
- Added placeholder docstrings to all Python modules
- Created `requirements.txt`, `.env.example`, and `.gitignore`
- Added `docs/` with project plan, architecture overview, scoring rules, and data sources
- Added `prompts/` to track Claude prompts used during development
- Confirmed: no trading execution, no broker integration, no ML, no web dashboard in v1
