import type { PortfolioSummary } from '../../types/portfolio'

interface PortfolioSelectorProps {
  portfolios: PortfolioSummary[]
  selectedId: number | null
  disabled: boolean
  onSelect: (id: number) => void
  onNew: () => void
}

/**
 * Portfolio picker: a native select plus a "New portfolio" action. Purely
 * presentational — all state lives in the parent container.
 */
export function PortfolioSelector({
  portfolios,
  selectedId,
  disabled,
  onSelect,
  onNew,
}: PortfolioSelectorProps) {
  return (
    <div className="portfolio-selector">
      <label className="field">
        <span className="field-label">Portfolio</span>
        <select
          className="text-input"
          value={selectedId ?? ''}
          disabled={disabled || portfolios.length === 0}
          onChange={(e) => onSelect(Number(e.target.value))}
          aria-label="Select portfolio"
        >
          {portfolios.length === 0 && <option value="">No portfolios yet</option>}
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.holdings_count})
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onNew}
        disabled={disabled}
      >
        New portfolio
      </button>
    </div>
  )
}
