"""
Market data fetcher.

Responsible for retrieving OHLCV price history, intraday quotes,
and volume data from configured providers (e.g. yfinance, Alpha Vantage).
Returns normalized pandas DataFrames consumed by the analysis layer.
"""
