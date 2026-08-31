import {
  formatMoney,
  formatSignedMoney,
  formatSignedPercent,
  gainLossTone,
} from '../../lib/portfolio'
import type { PaperAccountSummaryResponse } from '../../types/paperTrading'

interface PaperAccountSummaryCardsProps {
  summary: PaperAccountSummaryResponse
}

/**
 * Summary cards for a simulated account. Every value is pre-computed by the
 * backend summary service — nothing is recalculated here. A `null` total means
 * a held position could not be priced, so it renders as an em dash, not zero.
 */
export function PaperAccountSummaryCards({
  summary,
}: PaperAccountSummaryCardsProps) {
  return (
    <div className="portfolio-summary-cards" aria-label="Account summary">
      <div className="summary-card">
        <span className="summary-card-label">Cash balance</span>
        <span className="summary-card-value">
          {formatMoney(summary.cash_balance)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Open positions value</span>
        <span className="summary-card-value">
          {formatMoney(summary.open_positions_value)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Realized gain/loss</span>
        <span
          className={`summary-card-value tone-${gainLossTone(
            summary.realized_gain_loss,
          )}`}
        >
          {formatSignedMoney(summary.realized_gain_loss)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Unrealized gain/loss</span>
        <span
          className={`summary-card-value tone-${gainLossTone(
            summary.unrealized_gain_loss,
          )}`}
        >
          {formatSignedMoney(summary.unrealized_gain_loss)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Total value</span>
        <span className="summary-card-value">
          {formatMoney(summary.total_portfolio_value)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Total gain/loss</span>
        <span
          className={`summary-card-value tone-${gainLossTone(
            summary.total_return,
          )}`}
        >
          {formatSignedMoney(summary.total_return)}
          <span className="summary-card-sub">
            {formatSignedPercent(summary.total_return_percent)}
          </span>
        </span>
      </div>
    </div>
  )
}
