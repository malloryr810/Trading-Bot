import { Link } from 'react-router-dom'
import {
  analyzePath,
  formatMoney,
  formatPercent,
  formatShares,
  formatSignedMoney,
  formatSignedPercent,
  gainLossTone,
} from '../../lib/portfolio'
import type { HoldingValuation } from '../../types/portfolio'

interface HoldingsTableProps {
  holdings: HoldingValuation[]
  disabled: boolean
  onEdit: (holdingId: number) => void
  onRemove: (holdingId: number) => void
}

/**
 * Read-only holdings table. Every numeric column is a pre-computed backend
 * value formatted for display; no totals or returns are recalculated here.
 * Rows whose current price is unavailable render an explicit dash + tag.
 */
export function HoldingsTable({
  holdings,
  disabled,
  onEdit,
  onRemove,
}: HoldingsTableProps) {
  return (
    <div className="holdings-table-wrap">
      <table className="holdings-table">
        <thead>
          <tr>
            <th scope="col">Ticker</th>
            <th scope="col" className="num">Shares</th>
            <th scope="col" className="num">Avg cost</th>
            <th scope="col" className="num">Price</th>
            <th scope="col" className="num">Cost basis</th>
            <th scope="col" className="num">Market value</th>
            <th scope="col" className="num">Gain/loss</th>
            <th scope="col" className="num">Return</th>
            <th scope="col" className="num">Weight</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.holding_id}>
              <th scope="row" className="holding-ticker">
                {h.ticker}
                {!h.price_available && (
                  <span className="price-unavailable-tag" title="Current price unavailable">
                    no price
                  </span>
                )}
              </th>
              <td className="num">{formatShares(h.shares)}</td>
              <td className="num">{formatMoney(h.average_cost)}</td>
              <td className="num">{formatMoney(h.current_price)}</td>
              <td className="num">{formatMoney(h.cost_basis)}</td>
              <td className="num">{formatMoney(h.market_value)}</td>
              <td className={`num tone-${gainLossTone(h.unrealized_gain_loss)}`}>
                {formatSignedMoney(h.unrealized_gain_loss)}
              </td>
              <td className={`num tone-${gainLossTone(h.unrealized_return_pct)}`}>
                {formatSignedPercent(h.unrealized_return_pct)}
              </td>
              <td className="num">{formatPercent(h.weight_pct)}</td>
              <td>
                <div className="holding-actions">
                  <Link
                    to={analyzePath(h.ticker)}
                    className="btn btn-small btn-secondary"
                  >
                    Analyze
                  </Link>
                  <button
                    type="button"
                    className="btn btn-small btn-secondary"
                    onClick={() => onEdit(h.holding_id)}
                    disabled={disabled}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="btn btn-small btn-danger"
                    onClick={() => onRemove(h.holding_id)}
                    disabled={disabled}
                  >
                    Remove
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
