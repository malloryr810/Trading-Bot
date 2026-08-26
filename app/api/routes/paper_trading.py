"""
Paper trading routes — simulated trading only.

  POST /api/paper-trading/accounts                          — open an account
  GET  /api/paper-trading/accounts                          — list accounts
  GET  /api/paper-trading/accounts/{account_id}             — one account + positions
  GET  /api/paper-trading/accounts/{account_id}/summary     — valued summary
  GET  /api/paper-trading/accounts/{account_id}/positions   — priced open positions
  GET  /api/paper-trading/accounts/{account_id}/transactions — ledger, newest first
  POST /api/paper-trading/accounts/{account_id}/buy         — record a simulated buy
  POST /api/paper-trading/accounts/{account_id}/sell        — record a simulated sell

All routes delegate to the paper trading services; no persistence, accounting,
market-data, or calculation logic lives here.

Error mapping follows the existing repo style: not-found → 404, input
validation → 400, and a rejection that conflicts with current account state
(insufficient cash, insufficient shares) → 409, matching how a duplicate
portfolio holding is handled.  Malformed request bodies are rejected by
FastAPI with 422 before a route runs.  The summary and positions endpoints
return 200 even on partial (or complete) market-data failure — unavailable
prices surface in the response ``warnings`` list.

**Nothing here places a real order.** There is no broker integration, no real
account link, no automatic trading, no rebalancing, no alerting, no short
selling, no margin, and no options.  Every trade is a row the user typed in, at
a price the user supplied.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas.paper_trading import (
    AccountDetail,
    AccountSummary,
    AccountSummaryResponse,
    CreateAccountRequest,
    PositionsResponse,
    TradeRequest,
    TransactionResponse,
)
from app.services.paper_trading_service import (
    InsufficientFundsError,
    InsufficientSharesError,
    PaperTradingAccountNotFoundError,
    PaperTradingValidationError,
    create_account,
    get_account,
    list_accounts,
    list_transactions,
    record_buy,
    record_sell,
)
from app.services.paper_trading_summary_service import (
    get_account_summary,
    get_priced_positions,
)

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


@router.post("/accounts", response_model=AccountDetail, status_code=201)
async def post_account(request: CreateAccountRequest) -> dict:
    """Open a simulated trading account with a starting cash balance."""
    try:
        return create_account(request.name, request.starting_cash)
    except (PaperTradingValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/accounts", response_model=list[AccountSummary])
async def get_accounts() -> list[dict]:
    """Return all simulated trading accounts, newest first."""
    return list_accounts()


@router.get("/accounts/{account_id}", response_model=AccountDetail)
async def get_one_account(account_id: int) -> dict:
    """Return one account with its open positions (no market data)."""
    try:
        return get_account(account_id)
    except (PaperTradingAccountNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/accounts/{account_id}/summary", response_model=AccountSummaryResponse)
async def get_summary(account_id: int) -> dict:
    """Return the account valued at current prices.

    A missing account is 404.  Per-ticker market-data failures never fail the
    request: affected positions are marked ``price_available: false`` and listed
    in ``warnings``.
    """
    try:
        return get_account_summary(account_id)
    except (PaperTradingAccountNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/accounts/{account_id}/positions", response_model=PositionsResponse)
async def get_positions(account_id: int) -> dict:
    """Return the account's open positions with current-price calculations."""
    try:
        return get_priced_positions(account_id)
    except (PaperTradingAccountNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=list[TransactionResponse],
)
async def get_transactions(account_id: int) -> list[dict]:
    """Return the account's full transaction ledger, newest first."""
    try:
        return list_transactions(account_id)
    except (PaperTradingAccountNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/accounts/{account_id}/buy",
    response_model=TransactionResponse,
    status_code=201,
)
async def post_buy(account_id: int, request: TradeRequest) -> dict:
    """Record a simulated buy at the caller-supplied price.

    Insufficient cash is rejected with HTTP 409.
    """
    try:
        return record_buy(
            account_id,
            request.ticker,
            request.quantity,
            request.price,
            request.executed_at,
        )
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (PaperTradingAccountNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (PaperTradingValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/accounts/{account_id}/sell",
    response_model=TransactionResponse,
    status_code=201,
)
async def post_sell(account_id: int, request: TradeRequest) -> dict:
    """Record a simulated sell at the caller-supplied price.

    Selling more than the account holds — or a ticker it does not hold at all —
    is rejected with HTTP 409.  Short selling is not supported.
    """
    try:
        return record_sell(
            account_id,
            request.ticker,
            request.quantity,
            request.price,
            request.executed_at,
        )
    except InsufficientSharesError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (PaperTradingAccountNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (PaperTradingValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
