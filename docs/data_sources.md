# Data Sources

## Currently Used

| Source  | Data                          | Access method         |
|---------|-------------------------------|-----------------------|
| yfinance | Price history, basic fundamentals, options | pip package, no key required |

## Planned / Candidate Sources

| Source                  | Data                                  | Notes                          |
|-------------------------|---------------------------------------|--------------------------------|
| Alpha Vantage           | OHLCV, technicals, fundamentals       | Free tier available; key required |
| Polygon.io              | Real-time quotes, aggregates, news    | Free tier available; key required |
| Finnhub                 | News, sentiment, earnings, social     | Free tier available; key required |
| Financial Modeling Prep | Income statements, ratios, DCF        | Free tier available; key required |
| SEC EDGAR               | 10-K/10-Q filings, XBRL financials    | Public API, no key required    |
| NewsAPI                 | General news headlines                | Key required                   |

## Selection Criteria

- Prefer sources with a free tier sufficient for personal use
- Prefer sources with stable, versioned APIs and clear rate-limit documentation
- yfinance covers MVP needs; upgrade to a dedicated provider when reliability matters

## Key Management

All API keys are stored in `.env` (never committed) and accessed via `app/config.py`.
See `.env.example` for the expected variable names.
