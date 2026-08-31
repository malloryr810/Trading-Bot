import { Link } from 'react-router-dom'
import {
  analyzePath,
  formatMoney,
  formatShares,
  formatSignedMoney,
  formatSignedPercent,
  gainLossTone,
} from '../../lib/portfolio'
import type { PricedPaperPosition } from '../../types/paperTrading'

interface PaperPositionsTableProps {
  positions: PricedPaperPosition[]
}

/**
 * Open simulated positions. Quantity, average cost, and cost basis come from
 * the stored position row; price-dependent columns come from the summary
 * service. A position whose price is unavailable shows an em dash and a tag —
 * it is never displayed as a zero market value.
 */
export function PaperPositionsTable({ positions }: PaperPositionsTableProps) {
  return (
    <div className="holdings-table-wrap">
      <table className="holdings-table">
        <thead>
          <tr>
            <th scope="col">Ticker</th>
            <th scope="col" className="num">Quantity</th>
            <th scope="col" className="num">Avg cost</th>
            <th scope="col" className="num">Cost basis</th>
            <th scope="col" className="num">Price</th>
            <th scope="col" className="num">Market value</th>
            <th scope="col" className="num">Unrealized</th>
            <th scope="col" className="num">Return</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((position) => (
            <tr key={position.position_id}>
              <th scope="row" className="holding-ticker">
                {position.ticker}
                {!position.price_available && (
                  <span
                    className="price-unavailable-tag"
                    title="Current price unavailable"
                  >
                    no price
                  </span>
                )}
              </th>
              <td className="num">{formatShares(position.quantity)}</td>
              <td className="num">{formatMoney(position.average_cost)}</td>
              <td className="num">{formatMoney(position.cost_basis)}</td>
              <td className="num">{formatMoney(position.latest_price)}</td>
              <td className="num">{formatMoney(position.market_value)}</td>
              <td
                className={`num tone-${gainLossTone(
                  position.unrealized_gain_loss,
                )}`}
              >
                {formatSignedMoney(position.unrealized_gain_loss)}
              </td>
              <td
                className={`num tone-${gainLossTone(
                  position.unrealized_gain_loss_percent,
                )}`}
              >
                {formatSignedPercent(position.unrealized_gain_loss_percent)}
              </td>
              <td>
                <Link
                  to={analyzePath(position.ticker)}
                  className="btn btn-small btn-secondary"
                >
                  Analyze
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
