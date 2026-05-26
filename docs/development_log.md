# Development Log

## 2026-05-25 — Consolidate report formatters; remove legacy stock_report.py

**`app/reports/stock_report.py`** (removed)

- Deleted the older `generate_stock_report(ticker, rating, signals, ...)` formatter
- It had no production callers — `app/main.py` already used `build_stock_report` + `generate_plain_text_report` exclusively
- `app/reports/templates.py` is now the single canonical plain-text report implementation

**`tests/test_stock_report.py`** (removed)

- Deleted the 74-test suite that tested the legacy formatter only
- All meaningful coverage already existed in `test_report_templates.py` (header, recommendation, analysis summaries, signals ordering, key strengths/risks, triggers, disclaimer)
- Ticker validation is covered by `test_stock_report_model.py` at the Pydantic model level
- Tests for `_score_breakdown` and `rating.explanation` were specific to the legacy formatter's output; neither feature exists in `templates.py`

**`CLAUDE.md`** (updated)

- Removed `app/reports/stock_report.py` row from the "Currently Implemented" table

**`README.md`** (updated)

- Removed `stock_report.py` from the project structure block
- Updated test count from 1103 to 1029

No trading functionality added. Full suite 1029/1029 passing.

## 2026-05-25 — Code review, cleanup, and documentation update

**`app/utils/logging.py`** (removed)

- Removed empty docstring-only stub; nothing imported it and it contained no implementation

**`app/config.py`** (updated)

- Removed `OPENAI_API_KEY` and `DATABASE_URL` entries; both are aspirational for features that don't exist (no LLM, no database) and nothing imported config at all
- Retained `MARKET_DATA_API_KEY`, `NEWS_API_KEY`, `ENVIRONMENT`, and `DEBUG` as legitimate placeholders

**`CLAUDE.md`** (rewritten)

- Updated "Currently Implemented" table to include all implemented modules: `app/models/stock_report.py`, `app/reports/report_generator.py`, `app/reports/templates.py`, `app/reports/stock_report.py`, `app/watchlist.py`
- Removed "Not Yet Implemented" section (all three listed stubs are now implemented)
- Added all watchlist CLI commands and `--help`
- Added argparse note to `app/main.py` entry
- Added watchlist and argparse to development standards
- Added ML/LLM to the "Do not implement" list

**`README.md`** (rewritten)

- Added full feature list (all four signal categories, StockReport model, JSON export, watchlist scanning, watchlist export, argparse CLI)
- Added complete watchlist CLI usage section
- Added watchlist file format documentation
- Updated "What Is Not Included" section — removed "Watchlist scanning (planned, not yet built)" since it is now built; kept backtesting as future
- Updated test count from 812 to 1103
- Updated project structure to show all implemented files (no more stub labels)
- Added `outputs/` directory to structure
- Updated "Planned Future Work" section to accurately describe remaining roadmap items

No trading functionality added. Full suite 1103/1103 passing.

## 2026-05-25 — Refactor CLI to use argparse

**`app/main.py`** (updated)

- Replaced manual argument parsing with `argparse`; no product behavior changed
- Added `build_parser() -> argparse.ArgumentParser` — single source of truth for all flags and help text
- Added `parse_args(argv) -> argparse.Namespace` — thin public wrapper around `build_parser().parse_args(argv)`
- `main()` now calls `parser.parse_args(argv)` inside a `try/except SystemExit` so parse errors return 1 and `--help` returns 0 without propagating `SystemExit` to callers
- Mutual exclusion (ticker + `--watchlist` together) is validated after parsing; same "not both" error message preserved
- "No args" case validated after parsing; prints argparse-style usage to stderr and returns 1
- Removed manual `_USAGE` string constant
- All single-ticker and watchlist flags (`--save-report`, `--save-json`, `--watchlist`) preserved with identical behavior

**Tests updated**

- `tests/test_main.py`: Updated `test_no_ticker_prints_usage` to match argparse's lowercase `"usage:"` output (previously checked `"Usage"`)
- `tests/test_watchlist.py`: Updated `test_watchlist_flag_missing_path_returns_1` to check for `"--watchlist"` in stderr (argparse says `"argument --watchlist: expected one argument"`; previously checked `"requires a file path"`); updated `test_no_args_still_prints_usage` to lowercase `"usage"`

**Tests added**

- `tests/test_main.py` — `TestArgParser` (15 tests): unit tests for `parse_args()` covering single ticker, save flags, watchlist path, combined flags, no-args defaults, unknown flag raises SystemExit, `--help` raises SystemExit 0, flag order independence, and `build_parser()` return type
- `tests/test_main.py` — `TestMainBehaviorValidation` (11 tests): behavior tests for unknown flag returns 1 with "unrecognized" in stderr, `--help` returns 0 with expected text, ticker + watchlist mutual exclusion, no-args returns 1 with usage in stderr

**Intentional CLI behavior change**

Usage/error lines now use argparse's lowercase `"usage:"` prefix instead of the previous custom `"Usage:"`. All exit codes and error semantics are identical.

No trading functionality added. Full suite 1103/1103 passing (previously 1077, +26 tests).

## 2026-05-25 — Add watchlist save/export support

**`app/watchlist.py`** (updated)

- Added `serialize_watchlist_results(results) -> list[dict]` — converts `WatchlistResult` entries to JSON-serializable plain dicts; enum fields (`final_category`, `confidence_level`) serialized to their string values; `None` preserved as `null`; list order preserved for deterministic JSON output

**`app/main.py`** (updated)

- `_run_watchlist` accepts `do_save_report: bool` and `do_save_json: bool` parameters
- `--save-report`: saves the plain-text watchlist summary via `save_text_report(summary, "WATCHLIST")`; prints confirmation path; non-fatal on `StorageError`
- `--save-json`: saves `{"results": [...]}` dict via `save_json_result(data, "WATCHLIST")`; prints confirmation path; non-fatal on `StorageError`
- Both flags extracted before watchlist dispatch so they apply to both watchlist and single-ticker modes
- `_USAGE` updated to document all four flag combinations
- Single-ticker `--save-report`/`--save-json` behavior unchanged

**Tests added**

- `tests/test_watchlist.py` — 47 new tests across 5 new test classes: `TestWatchlistSaveReport` (8), `TestWatchlistSaveJson` (9), `TestWatchlistBothSaveFlags` (4), `TestSerializeWatchlistResults` (20), `TestSingleTickerSaveUnchanged` (3); also updated 4 existing flag-passing assertions to match new `_run_watchlist` signature (3 bool params)

No trading functionality added. Full suite 1077/1077 passing (previously 1030, +47 tests).

## 2026-05-25 — Add basic watchlist scanning

**`app/watchlist.py`** (new)

- `WatchlistLoadError` — raised for missing or empty watchlist files
- `WatchlistResult` dataclass — ticker, company_name, final_category, score, confidence_level, current_price, error_message; `succeeded` property distinguishes success from failure
- `load_watchlist(path)` — reads a plain-text file; strips whitespace; ignores blank lines and lines starting with `#`; normalizes tickers to uppercase; removes duplicates preserving first-seen order; raises `WatchlistLoadError` for missing files or no valid tickers
- `scan_watchlist(tickers, analyze_func)` — calls `analyze_func` for each ticker; captures failures as `WatchlistResult` entries with `error_message` set so one bad ticker never aborts the scan; returns successful results sorted by score descending followed by failures in encounter order; `analyze_func` is injectable so tests can avoid live API calls
- `format_watchlist_summary(results)` — renders an aligned plain-text table with TICKER / CATEGORY / SCORE / CONFIDENCE columns, error rows for failed tickers, and a footer with scanned/success/failed counts

**`watchlists/default.txt`** (new)

- Sample watchlist: AAPL, MSFT, NVDA, GOOGL, AMZN

**`app/main.py`** (updated)

- Added `--watchlist <file>` CLI flag; dispatches to `_run_watchlist` helper which loads the file, runs `scan_watchlist` via the existing `analyze_ticker` → `build_stock_report` pipeline, and prints the summary
- Single-ticker path and `--save-report`/`--save-json` flags unchanged
- Providing both a ticker and `--watchlist` prints an error and returns 1

**Tests added**

- `tests/test_watchlist.py` — 62 tests covering: file loading (normal, blank lines, comments, lowercase, dedup, whitespace, missing file, empty file); scan success, partial failure, all-failure, and ordering; format output (headers, counts, columns, error rows, order preservation); CLI integration (watchlist flag dispatch, missing path, ticker+watchlist conflict, partial failure returns 0, existing single-ticker path unaffected)

No trading functionality added. Full suite 1030/1030 passing (previously 968, +62 tests).

## 2026-05-25 — Implement structured report layer (StockReport model, templates, report generator)

**`app/models/stock_report.py`**

- Implemented `StockReport` Pydantic model: the top-level structured output of a full analysis run
- Fields: ticker (normalized, non-empty), company_name, current_price, final_category, score (0–100), confidence_level, per-category summaries, key_positive_factors, key_risks, buy_trigger, sell_or_avoid_trigger, data_timestamp, data_sources_used, and four per-category signal lists (technical_signals, fundamental_signals, news_signals, risk_signals)
- Reuses `RatingCategory`, `ConfidenceLevel`, and `Signal` from existing models; no concepts duplicated

**`app/reports/templates.py`**

- Implemented `format_plain_text_report(report: StockReport) -> str` — terminal-readable plain-text formatter
- Section structure matches existing CLI output style: header, recommendation, analysis summaries, signals (sorted Technical → Fundamental → News → Risk), key strengths, key risks, triggers, disclaimer
- Header now includes an "As of:" line from data_timestamp when present

**`app/reports/report_generator.py`**

- Implemented `build_stock_report(rating, company_name, current_price) -> StockReport` — assembles StockReport from a completed Rating; partitions `signals_used` into per-category lists; does not fetch data or perform analysis
- Implemented `generate_plain_text_report(report: StockReport) -> str` — delegates to `format_plain_text_report`

**`app/main.py`**

- Replaced `generate_stock_report` import and call with `build_stock_report` + `generate_plain_text_report`; no other changes; CLI flags and error handling unchanged

**Tests added**

- `tests/test_stock_report_model.py` — 42 tests: creation, ticker normalization, score/field validation, defaults, optional fields, immutability
- `tests/test_report_templates.py` — 52 tests: all report sections, signal ordering, count labels, trigger/risk/strength display, empty-state fallbacks
- `tests/test_report_generator.py` — 31 tests: field mapping from Rating, signal partitioning, optional parameters, generate_plain_text_report delegation

No trading functionality added. Full suite 968/968 passing (previously 842, +126 tests).

## 2026-05-24 — Remove dead format_rating_output() helper

- Confirmed via full-repo search: `format_rating_output()` was defined in `app/main.py` and tested in `tests/test_main.py` but never called by the production pipeline (which uses `generate_stock_report()`)
- Deleted `format_rating_output()` and its `# Formatting` section from `app/main.py`
- Removed `TestFormatRatingOutput` class (14 tests) from `tests/test_main.py`; removed `format_rating_output` from the import line
- No production behavior changed; `Rating` import retained (still used by `analyze_ticker` return annotation)
- Full suite 828/828 passing (−14 dead-code tests)

## 2026-05-24 — Consolidate shared helpers into app/utils/helpers.py

- Implemented `safe_float(value) -> float | None` and `normalize_ticker(ticker) -> str` in `app/utils/helpers.py`
- Removed `_safe_float` from `app/analysis/technicals.py`, `app/analysis/risk_analysis.py`, and `app/data/fundamentals.py`; all three copies were identical in behavior
- Removed `_validate_ticker` from `app/data/market_data.py`, `app/data/fundamentals.py`, `app/data/news_data.py`, and `app/data/storage.py`; all four copies were identical in behavior (storage.py used lowercase "ticker" in messages but module-boundary error types are unchanged)
- Each module now imports from `app.utils.helpers`; module-specific exception types (`DataFetchError`, `FundamentalDataFetchError`, `NewsFetchError`, `StorageError`) are preserved at public module boundaries via `try: normalize_ticker(ticker); except ValueError: raise ModuleError(...) from exc`
- Removed `import math` from `app/analysis/technicals.py` and `app/data/fundamentals.py` (only used by the removed helpers); kept in `app/analysis/risk_analysis.py` (`_validate_beta` uses `math.isfinite`)
- Added 29 tests in `tests/test_helpers.py` covering both helpers
- Full suite 842/842 passing

## 2026-05-24 — Codebase audit and cleanup

**`app/main.py`**

- Added `NewsAnalysisError` import and catch clause in `main()` — the error was reachable via `analyze_news()` but silently missing from the handler chain; now exits with `return 1` and a message to stderr like all other analysis errors

**`README.md`**

- Corrected test count (512 → 812), scoring table (News was listed as "reserved", now shown as 25% active), module table (added `news_data.py`, `news_analysis.py`, `models/news.py`, `storage.py`), CLI examples (`--save-report`, `--save-json`), project structure section; removed stale "Future Versions" mention of news analysis; added "What Is Not Included" section

**`tests/test_main.py`**

- Added `test_news_analysis_error_returns_1` to `TestMainErrors` — verifies `NewsAnalysisError` from `analyze_news` surfaces as exit code 1 with "news analysis" in stderr

**Refactor candidates (not changed — beyond audit scope)**

- `_safe_float` duplicated verbatim in `technicals.py`, `fundamentals_analysis.py`, `risk_analysis.py`, and `market_data.py` — move to `app/utils/helpers.py`
- `_validate_ticker` duplicated in `market_data.py`, `fundamentals.py`, `news_data.py`, `storage.py` — move to `app/utils/helpers.py`
- `format_rating_output()` in `main.py` — dead code; never called in the production pipeline (pipeline uses `generate_stock_report()`); 6 tests cover it, so it remains until those tests are removed
- `app/config.py` — defines `MARKET_DATA_API_KEY`, `NEWS_API_KEY`, `OPENAI_API_KEY`, `DATABASE_URL`; no module imports it; fields are unused placeholders
- `app/utils/helpers.py`, `app/utils/logging.py`, `app/models/stock_report.py`, `app/reports/report_generator.py`, `app/reports/templates.py` — docstring-only stubs; no production code depends on them

**Full suite 813/813 passing**

## 2026-05-24 — Report quality polish

**`app/analysis/scoring.py`**

- `_build_buy_trigger` and `_build_sell_avoid_trigger` now accept sub-scores and the active-category set; language no longer hardcodes "technical score" — triggers describe the weakest active category by name and reference the composite score
- `_build_positive_factors` now sorts by signal strength (STRONG → MODERATE → WEAK) so the highest-conviction factors appear first in the report
- `_build_risk_factors` now also includes cautionary neutral signals — those with `direction=NEUTRAL` and a description matching any keyword in `_CAUTION_KEYWORDS` (e.g. "elevated", "overbought", "warning"); capped at 10 items; bearish signals (score_impact < 0) are not double-counted
- `news_summary` now characterises sentiment qualitatively: "positive" (≥65), "moderately positive" (≥55), "mixed or neutral" (≥45), "cautionary" (≥35), "negative" (<35)
- Fixed stale docstring on `score_signals()` (previously said "NEWS signals are silently ignored")
- Added `_STRENGTH_ORDER`, `_CATEGORY_LABELS`, `_CAUTION_KEYWORDS`, `_weak_category_labels` helpers

**`app/reports/stock_report.py`**

- `_signals_section` now sorts signals by category before rendering: Technical → Fundamental → News → Risk; stable sort preserves within-category order; original list is not mutated

**Tests**

- `test_composite_scoring.py`: added `TestTriggers` (7 tests), `TestPositiveFactorsOrdering` (3 tests), `TestCautionaryNeutralRisks` (5 tests), `TestNewsSummaryQuality` (6 tests); added `RatingCategory` to imports
- `test_stock_report.py`: added `TestSignalsOrdering` (7 tests); added `_CATEGORY_ORDER` to imports
- Full suite 812/812 passing

## 2026-05-24 — CLI save flags

- Added `--save-report` and `--save-json` optional flags to `app/main.py`
- Default behavior unchanged: `python -m app.main AAPL` prints to terminal only, no files written
- `--save-report`: calls `save_text_report(report, ticker)` after printing; prints confirmation with saved path; `StorageError` handled gracefully (warning to stderr, exit 0)
- `--save-json`: calls `save_json_result(rating, ticker)` after printing; passes the `Rating` Pydantic model directly so all fields (ticker, score, category, confidence, sub-scores, signals) are serialised; prints confirmation with saved path; same graceful error handling
- Both flags can be combined: `python -m app.main AAPL --save-report --save-json`
- Updated module docstring with new usage examples
- Added 20 tests in `TestSaveFlags` class within `tests/test_main.py`; all mock storage functions — no real file writes
- Full suite 784/784 passing

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
