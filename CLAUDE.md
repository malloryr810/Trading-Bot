# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A modular Python investment analysis tool. It produces structured, scored research
reports for individual stocks. **It is not an automated trading system.** Do not
implement order execution, broker API calls, or live position management until
explicitly instructed after backtesting is complete.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the entry point
python app/main.py

# Run tests
pytest

# Run a specific test file
pytest tests/test_scoring.py
```

## Architecture

Data flows in one direction through four layers:

```
data/ → analysis/ → scoring.py → reports/
```

All inter-layer contracts are typed Pydantic models in `app/models/`.

| Layer | Package | Responsibility |
|-------|---------|---------------|
| Data | `app/data/` | Fetch and cache raw data; return DataFrames or Pydantic models |
| Analysis | `app/analysis/` | Produce `Signal` lists from raw data; modules are independent of each other |
| Scoring | `app/analysis/scoring.py` | Aggregate signals using weighted formula (see `docs/scoring_rules.md`) |
| Reports | `app/reports/` | Render a complete `StockReport` to disk |

**Scoring weights:** Technical 35% · Fundamental 25% · News/Sentiment 25% · Risk 15%

## Key Conventions

- All API keys and secrets live in `.env` (never committed). Access them only through `app/config.py`.
- Analysis modules (`technicals.py`, `fundamentals_analysis.py`, etc.) must not call each other — only `scoring.py` reads from multiple modules.
- New data providers should be swappable without touching analysis logic.
- `data/raw/`, `data/processed/`, and `data/reports/` are git-ignored; `.gitkeep` files preserve the folder structure.

## Docs

- `docs/project_plan.md` — version roadmap
- `docs/architecture.md` — full layer diagram
- `docs/scoring_rules.md` — score weights and rating thresholds
- `docs/data_sources.md` — provider options and selection criteria
- `docs/development_log.md` — append an entry for each meaningful change
