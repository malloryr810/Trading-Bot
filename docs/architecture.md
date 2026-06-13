# Architecture

## What This Is

A modular Python stock research decision-support tool. It analyzes individual
stocks and watchlists, producing scored plain-text research reports. It is not
an automated trading system and contains no broker integrations, order
execution, or position management.

> This document covers the core analysis pipeline (data → analysis → scoring →
> reports → CLI). The project also has a FastAPI backend, SQLite persistence
> (reports + watchlists), and a React + Vite frontend layered on top of the same
> services — see `CLAUDE.md` and `docs/full_stack_product_architecture.md` for
> the full-stack view.

## Design Principles

- **Modular** — each layer has a single responsibility and clean interfaces
- **Replaceable data sources** — swap providers without touching analysis logic
- **No hidden state** — data flows top-to-bottom; no shared mutable globals
- **Typed** — Pydantic models enforce structure at layer boundaries
- **Deterministic tests** — all tests use locally constructed data; no live API calls

## Data Flow

```
data/ → analysis/ → scoring.py → reports/
```

Data moves in one direction through four layers. No layer calls back into a
prior layer.

## Layer Map

```
main.py                            ← argparse CLI; orchestrates the pipeline
  │
  ├── data/                        ← fetch and validate raw data
  │   ├── market_data.py           ← OHLCV price history from yfinance
  │   ├── fundamentals.py          ← company fundamentals from yfinance
  │   ├── news_data.py             ← recent news headlines from yfinance
  │   └── storage.py               ← saves .txt, .md, and .json outputs to disk
  │
  ├── analysis/                    ← compute signals from data
  │   ├── technicals.py            ← SMA 20/50/200, RSI 14, MACD, volume SMA; 7 signals
  │   ├── fundamentals_analysis.py ← P/E, margins, growth, D/E, FCF; 5 signals
  │   ├── news_analysis.py         ← keyword sentiment, risk headlines, coverage; 3 signals
  │   ├── risk_analysis.py         ← volatility, drawdown, trend, liquidity, beta; 4–5 signals
  │   └── scoring.py               ← aggregates all signals into a composite Rating
  │
  ├── models/                      ← shared typed data structures (Pydantic)
  │   ├── signal.py                ← Signal model
  │   ├── rating.py                ← Rating model (output of scoring engine)
  │   ├── stock_report.py          ← StockReport model (top-level report output)
  │   ├── fundamentals.py          ← CompanyFundamentals model
  │   └── news.py                  ← NewsItem model
  │
  ├── reports/                     ← format and render output
  │   ├── report_generator.py      ← builds StockReport from a Rating
  │   └── templates.py             ← plain-text, Markdown, and watchlist formatters
  │
  ├── watchlist.py                 ← multi-ticker scanning and ranked summaries
  └── utils/
      └── helpers.py               ← safe_float, normalize_ticker
```

## Data Layer

Fetchers return normalized pandas DataFrames (`market_data.py`) or Pydantic
models (`fundamentals.py`, `news_data.py`). They do not perform analysis or
scoring. News fetch failures are non-fatal: `main.py` continues with an empty
news list.

`storage.py` writes outputs to disk:
- `outputs/reports/TICKER_YYYYMMDD_HHMMSS.txt` — plain-text reports
- `outputs/reports/TICKER_YYYYMMDD_HHMMSS.md` — Markdown reports
- `outputs/results/TICKER_YYYYMMDD_HHMMSS.json` — structured JSON results

## Analysis Layer

Each analysis module accepts a validated input (DataFrame or Pydantic model)
and returns a `list[Signal]`. Modules are independent of each other —
`technicals.py` does not call `fundamentals_analysis.py`, and so on.

`scoring.py` is the only module that reads across all four analysis outputs.
It aggregates signal impacts into a composite `Rating` using weighted sub-scores:

| Category    | Weight |
|-------------|--------|
| Technical   | 35%    |
| Fundamental | 25%    |
| News        | 25%    |
| Risk        | 15%    |

Weights are re-normalised to 100% when a category produces no signals.

## Reports Layer

`report_generator.py` takes a `Rating` and assembles a `StockReport` Pydantic
model by partitioning signals into per-category lists and mapping Rating fields
onto the StockReport contract. It does not re-score or re-analyse.

`templates.py` provides three public formatters:
- `format_plain_text_report(report)` — terminal-readable plain text (single ticker)
- `format_report_markdown(report)` — Markdown document (single ticker)
- `format_watchlist_markdown(results)` — Markdown document (watchlist scan)

Full pipeline flow for a single ticker:

```
analyze_ticker()
  → Rating
  → build_stock_report()
  → StockReport
  → format_plain_text_report()   (printed or --save-report)
  → format_report_markdown()     (--save-markdown)
```

## Watchlist Flow

```
watchlist file
  → load_watchlist()
  → scan_watchlist()        ← runs single-stock pipeline for each ticker
  → ranked summary table    ← sorted by composite score, includes company name and price
  → optional .txt export    (--save-report)
  → optional .md export     (--save-markdown)
  → optional .json export   (--save-json)
```

`watchlist.py` reuses the single-stock pipeline for each ticker and adds no
analysis logic of its own.

## CLI

`main.py` uses `argparse` with five flags:

| Flag              | Effect |
|-------------------|--------|
| `TICKER`          | Analyze a single ticker symbol |
| `--watchlist FILE`| Scan all tickers in a plain-text watchlist file |
| `--save-report`   | Save plain-text output to `outputs/reports/` |
| `--save-markdown` | Save Markdown output to `outputs/reports/` |
| `--save-json`     | Save structured JSON to `outputs/results/` |

All three save flags apply to both single-ticker and watchlist modes.
`TICKER` and `--watchlist` are mutually exclusive; at least one must
be provided.

## Models Layer

Pydantic models (`Signal`, `Rating`, `StockReport`, `CompanyFundamentals`,
`NewsItem`) act as typed contracts between layers. Any layer may import them;
no layer owns them exclusively.

## Testing Approach

All tests are deterministic. Tests construct DataFrames and Pydantic
models locally — no live yfinance or API calls. Analysis modules receive
pre-built inputs; data fetchers are tested against locally constructed mock
data, never against the network.
