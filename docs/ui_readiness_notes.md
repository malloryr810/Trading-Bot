# UI Readiness Notes

## Intended UI Path

```
CLI (app/main.py)
    ↓
Service layer (app/services/stock_analysis_service.py)
    ↓
Streamlit UI  ← next milestone
    ↓
FastAPI + React  ← optional, later
```

The service layer is the stable contract. All future UI work should call the
service functions directly. Neither a Streamlit app nor a FastAPI backend should
import from `app/main.py`.

---

## Public Service API

These three functions in `app/services/stock_analysis_service.py` are the
intended entry points for any UI layer:

| Function | Return type | Use case |
|---|---|---|
| `analyze_stock(ticker)` | `StockReport` | Single-ticker analysis; returns a fully assembled, render-ready object |
| `analyze_ticker(ticker)` | `Rating` | Lower-level; returns the raw scored rating without the assembled report fields |
| `analyze_watchlist_file(path)` | `list[WatchlistResult]` | Scan a watchlist file; results are sorted by score descending |

**For a Streamlit UI, prefer `analyze_stock` and `analyze_watchlist_file`.** The
`StockReport` model already partitions signals by category, includes summaries,
strengths, risks, and triggers — everything a UI needs to render without further
assembly.

---

## StockReport Fields Available to a UI

```python
stock_report.ticker                  # str
stock_report.company_name            # str | None
stock_report.current_price           # float | None
stock_report.final_category          # RatingCategory enum
stock_report.score                   # float (0–100)
stock_report.confidence_level        # ConfidenceLevel enum
stock_report.technical_summary       # str | None
stock_report.fundamental_summary     # str | None
stock_report.news_summary            # str | None
stock_report.risk_summary            # str | None
stock_report.key_positive_factors    # list[str]
stock_report.key_risks               # list[str]
stock_report.buy_trigger             # str | None
stock_report.sell_or_avoid_trigger   # str | None
stock_report.technical_signals       # list[Signal]
stock_report.fundamental_signals     # list[Signal]
stock_report.news_signals            # list[Signal]
stock_report.risk_signals            # list[Signal]
stock_report.confidence_diagnostics  # ConfidenceDiagnostics | None
stock_report.data_timestamp          # datetime | None
stock_report.data_sources_used       # list[str]
```

`StockReport` is a Pydantic model and is fully JSON-serializable via
`stock_report.model_dump_json()` or `stock_report.model_dump(mode="json")`.

---

## WatchlistResult Fields Available to a UI

```python
result.ticker           # str
result.company_name     # str | None
result.final_category   # RatingCategory | None
result.score            # float | None
result.confidence_level # ConfidenceLevel | None
result.current_price    # float | None
result.error_message    # str | None  (set on failure)
result.succeeded        # bool property
```

---

## Error Handling Contract

The service functions raise typed exceptions. A UI should catch them and display
user-friendly messages without crashing:

| Exception | Source | Meaning |
|---|---|---|
| `DataFetchError` | `app.data.market_data` | Price data unavailable (bad ticker, network) |
| `FundamentalDataFetchError` | `app.data.fundamentals` | Fundamental data unavailable |
| `TechnicalAnalysisError` | `app.analysis.technicals` | Cannot compute technical indicators |
| `FundamentalAnalysisError` | `app.analysis.fundamentals_analysis` | Cannot compute fundamental signals |
| `RiskAnalysisError` | `app.analysis.risk_analysis` | Cannot compute risk signals |
| `NewsAnalysisError` | `app.analysis.news_analysis` | Cannot compute news signals |
| `ScoringError` | `app.analysis.scoring` | Cannot score signals |

News fetch failure is **non-fatal** — the pipeline continues with neutral news
signals. All other exceptions abort the run and should be shown as an error.

For `analyze_watchlist_file`, per-ticker failures are captured inside
`WatchlistResult.error_message` and never raise — the function only raises
`WatchlistLoadError` if the file is missing or empty.

---

## What NOT to Do Yet

- Do not build a Streamlit UI until the service API has been stable for a few
  runs and the JSON output format is confirmed.
- Do not add live trading, broker API calls, order execution, or position
  management. This project is a **decision-support tool only**.
- Do not add a FastAPI layer before the Streamlit UI is stable. Add API serving
  only if you need to serve multiple concurrent clients.
- Do not add auto-refresh / live polling. All data fetches are point-in-time.
- Do not add an advanced dashboard (multi-chart, portfolio aggregation) before
  the single-ticker and watchlist views are working end-to-end.
- Do not add ML or LLM sentiment models.

---

## Current JSON Export Format

The `--save-json` CLI flag now exports a `StockReport` (as of the
service-boundary cleanup pass). The `StockReport` model is richer than the
previous `Rating` export: it includes partitioned signal lists and per-category
summaries. Any script that parsed the old `Rating`-based JSON will need to be
updated to use the new field names (`confidence_level` instead of `confidence`,
partitioned signal lists instead of `signals_used`).

---

## Known Future Cleanup Items

- `test_main.py` contains a `TestAnalyzeTicker` class that exercises the service
  function via a re-export. These tests are redundant with
  `test_stock_analysis_service.py` and should be consolidated into the service
  test file in a future pass.
- The `analyze_ticker` (→ `Rating`) function is lower-level than most UI callers
  need. Consider deprecating it as a public API once no callers outside the
  service itself need it.
