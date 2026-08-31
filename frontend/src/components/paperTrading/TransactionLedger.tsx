import {
  formatMoney,
  formatShares,
  formatSignedMoney,
  gainLossTone,
} from '../../lib/portfolio'
import { formatTimestamp } from '../../lib/format'
import {
  transactionTypeLabel,
  transactionTypeTone,
} from '../../lib/paperTrading'
import type { PaperTransaction } from '../../types/paperTrading'

interface TransactionLedgerProps {
  transactions: PaperTransaction[]
}

/**
 * Append-only simulated trade ledger, newest first as returned by the backend
 * (the order is not re-sorted here). `realized_gain_loss` is always 0 on a buy.
 */
export function TransactionLedger({ transactions }: TransactionLedgerProps) {
  return (
    <div className="holdings-table-wrap">
      <table className="holdings-table">
        <thead>
          <tr>
            <th scope="col">Type</th>
            <th scope="col">Ticker</th>
            <th scope="col" className="num">Quantity</th>
            <th scope="col" className="num">Price</th>
            <th scope="col" className="num">Gross</th>
            <th scope="col" className="num">Realized</th>
            <th scope="col">Executed</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => (
            <tr key={tx.id}>
              <td>
                <span
                  className={`trade-tag trade-tag-${transactionTypeTone(
                    tx.transaction_type,
                  )}`}
                >
                  {transactionTypeLabel(tx.transaction_type)}
                </span>
              </td>
              <th scope="row" className="holding-ticker">
                {tx.ticker}
              </th>
              <td className="num">{formatShares(tx.quantity)}</td>
              <td className="num">{formatMoney(tx.price)}</td>
              <td className="num">{formatMoney(tx.gross_amount)}</td>
              <td className={`num tone-${gainLossTone(tx.realized_gain_loss)}`}>
                {formatSignedMoney(tx.realized_gain_loss)}
              </td>
              <td>{formatTimestamp(tx.executed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
