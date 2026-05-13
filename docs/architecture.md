# Architecture

## Design Principles

- **Modular** — each layer has a single responsibility and clean interfaces
- **Replaceable data sources** — swap providers without touching analysis logic
- **No hidden state** — data flows top-to-bottom; no shared mutable globals
- **Typed** — Pydantic models enforce structure at layer boundaries

## Layer Map

```
main.py
  │
  ├── data/           ← fetch & persist raw data
  │   ├── market_data.py
  │   ├── fundamentals.py
  │   ├── news_data.py
  │   └── storage.py
  │
  ├── analysis/       ← transform data into signals & scores
  │   ├── technicals.py
  │   ├── fundamentals_analysis.py
  │   ├── news_analysis.py
  │   ├── risk_analysis.py
  │   └── scoring.py
  │
  ├── models/         ← shared typed data structures
  │   ├── signal.py
  │   ├── rating.py
  │   └── stock_report.py
  │
  └── reports/        ← render final output
      ├── report_generator.py
      └── templates.py
```

## Data Layer

Fetchers return normalized pandas DataFrames or Pydantic models.
`storage.py` handles caching to `data/raw/` so repeated runs do not
re-hit APIs unnecessarily.

## Analysis Layer

Each module reads from the data layer and emits a list of `Signal` objects.
Modules are independent — technicals does not call fundamentals_analysis.
`scoring.py` is the only module that reads from multiple analysis modules.

## Reports Layer

`report_generator.py` receives a complete `StockReport` model and writes
a formatted file. Templates are separated so the format (Markdown, HTML,
plain text) can change without touching generation logic.

## Models Layer

Pydantic models (`Signal`, `Rating`, `StockReport`) act as typed contracts
between layers. Any layer can import them; no layer owns them exclusively.

## Future Trading Layer (not yet implemented)

A future `trading/` package will sit alongside `app/` and will only be
reachable after the analysis pipeline is proven against historical data.
It will require explicit confirmation before placing any order.
