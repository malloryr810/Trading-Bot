import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listDiscoveryModes,
  listDiscoveryUniverses,
  runDiscovery,
} from '../api/discoveryApi'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/layout/PageHeader'
import { DiscoveryCandidateCard } from '../components/discovery/DiscoveryCandidateCard'
import { DiscoveryControls } from '../components/discovery/DiscoveryControls'
import { DiscoveryWarnings } from '../components/discovery/DiscoveryWarnings'
import {
  DEFAULT_DISCOVERY_QUERY,
  clampLimit,
  emptyResultsMessage,
  runSummary,
} from '../lib/discovery'
import { getErrorMessage } from '../lib/errors'
import { formatTimestamp } from '../lib/format'
import type {
  DiscoveryModeInfo,
  DiscoveryQuery,
  DiscoveryRun,
  DiscoveryUniverseInfo,
} from '../types/discovery'

export function DiscoverPage() {
  const [query, setQuery] = useState<DiscoveryQuery>(DEFAULT_DISCOVERY_QUERY)
  const [modes, setModes] = useState<DiscoveryModeInfo[]>([])
  const [universes, setUniverses] = useState<DiscoveryUniverseInfo[]>([])
  const [optionsError, setOptionsError] = useState<string | null>(null)

  const [run, setRun] = useState<DiscoveryRun | null>(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  // Load the control options once. Modes and universes are independent, so they
  // are fetched in parallel. State is only set inside async callbacks so the
  // effect never cascades on mount.
  useEffect(() => {
    let active = true
    Promise.all([listDiscoveryModes(), listDiscoveryUniverses()])
      .then(([modeList, universeList]) => {
        if (!active) return
        setModes(modeList)
        setUniverses(universeList)
        setOptionsError(null)
      })
      .catch((err: unknown) => {
        if (active)
          setOptionsError(
            getErrorMessage(err, 'Could not load discovery options.'),
          )
      })
    return () => {
      active = false
    }
  }, [])

  function handleQueryChange(next: DiscoveryQuery) {
    setQuery({
      ...next,
      limit: clampLimit(next.limit, next.maxFullAnalysis),
    })
  }

  async function handleRun() {
    setRunning(true)
    setRunError(null)
    setRun(null)
    try {
      setRun(await runDiscovery(query))
    } catch (err) {
      setRunError(getErrorMessage(err, 'Discovery failed — please try again.'))
    } finally {
      setRunning(false)
    }
  }

  const hasResults = run !== null && run.results.length > 0

  return (
    <div className="page">
      <PageHeader
        title="Discover"
        subtitle="Rule-based, data-driven research candidates ranked from a controlled stock universe. Every score and factor comes from the same analysis engine used on the Analyze page — this is not financial advice, and nothing here is traded."
      />

      {optionsError && <ErrorMessage message={optionsError} />}

      <DiscoveryControls
        query={query}
        modes={modes}
        universes={universes}
        running={running}
        onChange={handleQueryChange}
        onRun={handleRun}
      />

      {running && (
        <LoadingState message="Screening the universe and analyzing the shortlist — this can take a minute…" />
      )}
      {runError && <ErrorMessage message={runError} />}

      {!running && !runError && run === null && (
        <p className="empty-state">
          Choose a mode and run discovery to see ranked candidates. Nothing is
          scanned automatically and nothing is saved.
        </p>
      )}

      {run && !running && (
        <section className="discovery-results" aria-label="Discovery results">
          <div className="discovery-results-head">
            <h2 className="section-title">Ranked candidates</h2>
            <span className="discovery-results-meta">
              Run finished {formatTimestamp(run.completed_at)} · sources:{' '}
              {run.data_sources_used.join(', ') || 'none reported'}
            </span>
          </div>
          <p className="discovery-run-summary">{runSummary(run)}</p>

          {hasResults ? (
            <ul className="discovery-grid">
              {run.results.map((candidate) => (
                <DiscoveryCandidateCard
                  key={candidate.ticker}
                  candidate={candidate}
                />
              ))}
            </ul>
          ) : (
            <p className="empty-state">{emptyResultsMessage(run)}</p>
          )}

          <DiscoveryWarnings warnings={run.warnings} />
        </section>
      )}

      <p>
        <Link to="/">← Back to Dashboard</Link>
      </p>
    </div>
  )
}
