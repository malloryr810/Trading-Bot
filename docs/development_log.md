# Development Log

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
