import { Link } from 'react-router-dom'
import {
  candidateSubtitle,
  categoryTone,
  formatPrice,
  formatScore,
} from '../../lib/discovery'
import { analyzePath } from '../../lib/portfolio'
import type { DiscoveryCandidate } from '../../types/discovery'

interface DiscoveryCandidateCardProps {
  candidate: DiscoveryCandidate
}

interface SubScore {
  label: string
  value: number
}

/**
 * One ranked discovery result. Presentational only: every score, category,
 * factor, and reason shown here comes from the backend as-is.
 */
export function DiscoveryCandidateCard({
  candidate,
}: DiscoveryCandidateCardProps) {
  const subtitle = candidateSubtitle(candidate)
  const subScores: SubScore[] = [
    { label: 'Technical', value: candidate.technical_score },
    { label: 'Fundamental', value: candidate.fundamental_score },
    { label: 'News', value: candidate.news_score },
    { label: 'Risk', value: candidate.risk_score },
  ]

  return (
    <li className="discovery-card">
      <div className="discovery-card-top">
        <span className="discovery-rank" aria-label={`Rank ${candidate.rank}`}>
          {candidate.rank}
        </span>
        <div className="discovery-identity">
          <span className="discovery-ticker">{candidate.ticker}</span>
          {subtitle && <span className="discovery-subtitle">{subtitle}</span>}
        </div>
        <div className="discovery-headline-values">
          <span className="discovery-score">{formatScore(candidate.score)}</span>
          <span className="discovery-score-label">score</span>
        </div>
      </div>

      <div className="discovery-verdict">
        <span
          className={`category-badge category-badge--${categoryTone(candidate.final_category)}`}
        >
          {candidate.final_category}
        </span>
        <span className="discovery-confidence">
          {candidate.confidence_level} confidence
        </span>
        <span className="discovery-price">
          {formatPrice(candidate.current_price)}
        </span>
      </div>

      <p className="discovery-reason">{candidate.match_reason}</p>

      <ul className="discovery-subscores">
        {subScores.map((sub) => (
          <li key={sub.label} className="discovery-subscore">
            <span className="discovery-subscore-value">
              {formatScore(sub.value)}
            </span>
            <span className="discovery-subscore-label">{sub.label}</span>
          </li>
        ))}
      </ul>

      <div className="discovery-factors">
        <div className="discovery-factor-group">
          <h4 className="discovery-factor-title">Key positives</h4>
          {candidate.key_positive_factors.length === 0 ? (
            <p className="discovery-factor-empty">None reported.</p>
          ) : (
            <ul className="discovery-factor-list">
              {candidate.key_positive_factors.map((factor) => (
                <li key={factor}>{factor}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="discovery-factor-group">
          <h4 className="discovery-factor-title">Key risks</h4>
          {candidate.key_risks.length === 0 ? (
            <p className="discovery-factor-empty">None reported.</p>
          ) : (
            <ul className="discovery-factor-list">
              {candidate.key_risks.map((risk) => (
                <li key={risk}>{risk}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {(candidate.buy_trigger || candidate.sell_or_avoid_trigger) && (
        <dl className="discovery-triggers">
          {candidate.buy_trigger && (
            <div className="discovery-trigger">
              <dt>What would confirm it</dt>
              <dd>{candidate.buy_trigger}</dd>
            </div>
          )}
          {candidate.sell_or_avoid_trigger && (
            <div className="discovery-trigger">
              <dt>What would invalidate it</dt>
              <dd>{candidate.sell_or_avoid_trigger}</dd>
            </div>
          )}
        </dl>
      )}

      <div className="discovery-card-actions">
        <Link
          className="btn btn-secondary btn-small"
          to={analyzePath(candidate.ticker)}
        >
          Analyze {candidate.ticker}
        </Link>
      </div>
    </li>
  )
}
