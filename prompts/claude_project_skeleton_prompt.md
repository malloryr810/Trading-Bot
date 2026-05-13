# Prompt: Project Skeleton

## Used on
2026-05-12

## Summary

Asked Claude Code to create the initial modular project skeleton for a personal
investment analysis bot in Python.

## Key requirements provided

- Modular structure: data / analysis / reports / models / utils layers
- Python with pandas, numpy, yfinance, pydantic, python-dotenv, pytest
- Placeholder docstrings on all modules; no real implementation yet
- app/main.py must be minimally runnable
- config.py loads env vars via python-dotenv; no hardcoded secrets
- .env.example with placeholder keys
- .gitignore preserving empty data/ folders via .gitkeep
- docs/ covering project plan, architecture, scoring rules, data sources, dev log
- prompts/ to track Claude prompts used during development
- No trading execution, broker integration, ML, or web dashboard in v1

## Constraints enforced

- Do not implement trading execution
- Do not add broker integration
- Do not add machine learning
- Do not create a web dashboard
- Do not over-engineer or add unnecessary dependencies
- Do not hardcode secrets or API keys
