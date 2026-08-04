import {
  DISCOVERY_MODES,
  LIMIT_CHOICES,
  modeLabel,
} from '../../lib/discovery'
import type {
  DiscoveryMode,
  DiscoveryModeInfo,
  DiscoveryQuery,
  DiscoveryUniverseInfo,
} from '../../types/discovery'

interface DiscoveryControlsProps {
  query: DiscoveryQuery
  modes: DiscoveryModeInfo[]
  universes: DiscoveryUniverseInfo[]
  running: boolean
  onChange: (next: DiscoveryQuery) => void
  onRun: () => void
}

/**
 * Presentational control bar for the Discover page. It only edits the query
 * object — it never runs, screens, or ranks anything itself.
 */
export function DiscoveryControls({
  query,
  modes,
  universes,
  running,
  onChange,
  onRun,
}: DiscoveryControlsProps) {
  const modeKeys: DiscoveryMode[] =
    modes.length > 0 ? modes.map((m) => m.key) : DISCOVERY_MODES
  const activeMode = modes.find((m) => m.key === query.mode)

  return (
    <section className="discovery-controls" aria-label="Discovery controls">
      <div className="discovery-control-row">
        <label className="field">
          <span className="field-label">Mode</span>
          <select
            className="text-input"
            value={query.mode}
            disabled={running}
            onChange={(e) =>
              onChange({ ...query, mode: e.target.value as DiscoveryMode })
            }
          >
            {modeKeys.map((key) => (
              <option key={key} value={key}>
                {modes.find((m) => m.key === key)?.label ?? modeLabel(key)}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">Universe</span>
          <select
            className="text-input"
            value={query.universe}
            disabled={running || universes.length === 0}
            onChange={(e) => onChange({ ...query, universe: e.target.value })}
          >
            {universes.length === 0 ? (
              <option value={query.universe}>{query.universe}</option>
            ) : (
              universes.map((universe) => (
                <option key={universe.key} value={universe.key}>
                  {universe.name} ({universe.size})
                </option>
              ))
            )}
          </select>
        </label>

        <label className="field">
          <span className="field-label">Results</span>
          <select
            className="text-input"
            value={query.limit}
            disabled={running}
            onChange={(e) =>
              onChange({ ...query, limit: Number(e.target.value) })
            }
          >
            {LIMIT_CHOICES.map((choice) => (
              <option key={choice} value={choice}>
                Top {choice}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="btn btn-primary discovery-run-btn"
          onClick={onRun}
          disabled={running}
        >
          {running ? 'Scanning…' : 'Run discovery'}
        </button>
      </div>

      {activeMode && (
        <p className="discovery-mode-help">
          <strong>{activeMode.label}:</strong> {activeMode.description}{' '}
          <span className="discovery-mode-ranking">
            Ranked by: {activeMode.ranking}
          </span>
        </p>
      )}

      <p className="action-hint">
        Each run analyzes at most {query.maxFullAnalysis} tickers from the
        selected universe, so a scan takes a few seconds per ticker.
      </p>
    </section>
  )
}
