import { warningsSummary } from '../../lib/discovery'
import type { DiscoveryWarning } from '../../types/discovery'

interface DiscoveryWarningsProps {
  warnings: DiscoveryWarning[]
}

const STAGE_LABEL: Record<DiscoveryWarning['stage'], string> = {
  prescreen: 'pre-screen',
  analysis: 'analysis',
}

/**
 * Per-ticker skips from a partially successful run. Presentational only —
 * these are the warnings the backend returned, not client-side judgements.
 */
export function DiscoveryWarnings({ warnings }: DiscoveryWarningsProps) {
  if (warnings.length === 0) return null

  return (
    <section className="discovery-warnings" aria-label="Skipped tickers">
      <h3 className="discovery-warnings-title">{warningsSummary(warnings)}</h3>
      <p className="action-hint">
        These tickers were skipped without failing the run — usually missing or
        unusable market data.
      </p>
      <ul className="discovery-warning-list">
        {warnings.map((warning) => (
          <li key={`${warning.stage}-${warning.ticker}`} className="discovery-warning-item">
            <span className="discovery-warning-ticker">{warning.ticker}</span>
            <span className="discovery-warning-stage">
              {STAGE_LABEL[warning.stage]}
            </span>
            <span className="discovery-warning-msg">{warning.message}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
