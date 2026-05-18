# Development Log

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
