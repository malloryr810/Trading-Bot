import { formatMoney, formatSignedMoney, gainLossTone } from '../../lib/portfolio'
import { accountPositionsLabel } from '../../lib/paperTrading'
import type { PaperAccountSummary } from '../../types/paperTrading'

interface PaperAccountSelectorProps {
  accounts: PaperAccountSummary[]
  selectedId: number | null
  disabled: boolean
  onSelect: (id: number) => void
}

/**
 * Simulated account picker. Every figure shown is a stored backend value —
 * cash balance and realized gain/loss are maintained by the accounting service.
 */
export function PaperAccountSelector({
  accounts,
  selectedId,
  disabled,
  onSelect,
}: PaperAccountSelectorProps) {
  return (
    <ul className="paper-account-list">
      {accounts.map((account) => (
        <li key={account.id}>
          <button
            type="button"
            className={`paper-account-card${
              account.id === selectedId ? ' is-selected' : ''
            }`}
            onClick={() => onSelect(account.id)}
            disabled={disabled}
            aria-pressed={account.id === selectedId}
          >
            <span className="paper-account-name">{account.name}</span>
            <span className="paper-account-cash">
              {formatMoney(account.cash_balance)}
              <span className="paper-account-cash-label"> cash</span>
            </span>
            <span className="paper-account-meta">
              <span>Started {formatMoney(account.starting_cash)}</span>
              <span
                className={`tone-${gainLossTone(account.realized_gain_loss)}`}
              >
                Realized {formatSignedMoney(account.realized_gain_loss)}
              </span>
              <span>{accountPositionsLabel(account.positions_count)}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
