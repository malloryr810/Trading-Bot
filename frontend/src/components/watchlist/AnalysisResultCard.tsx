import { pickPrimarySummary } from '../../lib/watchlist'
import type { WatchlistAnalysisResult } from '../../types/watchlist'

interface AnalysisResultCardProps {
  result: WatchlistAnalysisResult
  /** 1-based rank within the best-score-first ordering. */
  rank: number
}

/**
 * One on-demand analysis result. Presentational only — it renders backend
 * values (category, score, confidence, price) and never recomputes them.
 */
export function AnalysisResultCard({ result, rank }: AnalysisResultCardProps) {
  const summary = pickPrimarySummary(result.report)
  return (
    <li className="analysis-result-card">
      <div className="analysis-result-top">
        <span className="analysis-result-rank" aria-hidden="true">
          {rank}
        </span>
        <div className="analysis-result-id">
          <span className="analysis-result-ticker">{result.ticker}</span>
          {result.company_name && (
            <span className="analysis-result-company">
              {result.company_name}
            </span>
          )}
        </div>
        <span className="analysis-result-score">{result.score.toFixed(1)}</span>
      </div>

      <div className="analysis-result-verdict">
        <span className="category-badge">{result.category}</span>
        <span className="analysis-result-confidence">{result.confidence}</span>
        {result.current_price != null && (
          <span className="analysis-result-price">
            ${result.current_price.toFixed(2)}
          </span>
        )}
      </div>

      {summary && <p className="analysis-result-summary">{summary}</p>}
    </li>
  )
}
