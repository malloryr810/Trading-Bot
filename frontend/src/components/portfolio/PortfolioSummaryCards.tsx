import {
  formatMoney,
  formatSignedMoney,
  formatSignedPercent,
  gainLossTone,
} from '../../lib/portfolio'
import type { PortfolioSummaryResponse } from '../../types/portfolio'

interface PortfolioSummaryCardsProps {
  summary: PortfolioSummaryResponse
}

/**
 * Summary cards for a priced portfolio. All values come pre-computed from the
 * backend summary endpoint — nothing is recalculated here.
 */
export function PortfolioSummaryCards({ summary }: PortfolioSummaryCardsProps) {
  const glTone = gainLossTone(summary.total_unrealized_gain_loss)
  const returnTone = gainLossTone(summary.total_unrealized_return_pct)

  return (
    <div className="portfolio-summary-cards" aria-label="Portfolio summary">
      <div className="summary-card">
        <span className="summary-card-label">Market value</span>
        <span className="summary-card-value">
          {formatMoney(summary.total_market_value)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Cost basis</span>
        <span className="summary-card-value">
          {formatMoney(summary.total_cost_basis)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Unrealized gain/loss</span>
        <span className={`summary-card-value tone-${glTone}`}>
          {formatSignedMoney(summary.total_unrealized_gain_loss)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Unrealized return</span>
        <span className={`summary-card-value tone-${returnTone}`}>
          {formatSignedPercent(summary.total_unrealized_return_pct)}
        </span>
      </div>
      <div className="summary-card">
        <span className="summary-card-label">Holdings</span>
        <span className="summary-card-value">{summary.holdings_count}</span>
      </div>
    </div>
  )
}
