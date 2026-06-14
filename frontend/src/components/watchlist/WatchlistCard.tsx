import { formatDate } from '../../lib/format'
import type { WatchlistSummary } from '../../types/watchlist'

interface WatchlistCardProps {
  watchlist: WatchlistSummary
  selected: boolean
  disabled: boolean
  onSelect: (id: number) => void
}

/** Overview card for one saved watchlist in the list grid. */
export function WatchlistCard({
  watchlist,
  selected,
  disabled,
  onSelect,
}: WatchlistCardProps) {
  const { ticker_count: count } = watchlist
  return (
    <button
      type="button"
      className={`watchlist-card${selected ? ' is-selected' : ''}`}
      onClick={() => onSelect(watchlist.id)}
      disabled={disabled}
      aria-pressed={selected}
    >
      <span className="watchlist-card-head">
        <span className="watchlist-card-name">{watchlist.name}</span>
        <span className="watchlist-card-count" aria-hidden="true">
          {count}
        </span>
      </span>
      {watchlist.description && (
        <span className="watchlist-card-desc">{watchlist.description}</span>
      )}
      <span className="watchlist-card-meta">
        {count === 1 ? '1 ticker' : `${count} tickers`} · Updated{' '}
        {formatDate(watchlist.updated_at)}
      </span>
    </button>
  )
}
