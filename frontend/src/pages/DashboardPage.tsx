import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { checkHealth } from '../api/analysisApi'

type HealthStatus = 'checking' | 'ok' | 'unavailable'

export function DashboardPage() {
  const [healthStatus, setHealthStatus] = useState<HealthStatus>('checking')

  useEffect(() => {
    checkHealth()
      .then(() => setHealthStatus('ok'))
      .catch(() => setHealthStatus('unavailable'))
  }, [])

  return (
    <div className="page">
      <h1>Investment Bot</h1>
      <p className="subtitle">
        Personal stock research and decision-support tool.
      </p>

      <div
        className={`health-indicator health-${healthStatus}`}
        role="status"
        aria-live="polite"
      >
        {healthStatus === 'checking' && 'Checking backend…'}
        {healthStatus === 'ok' && '✓ Backend connected'}
        {healthStatus === 'unavailable' &&
          'Backend unavailable — start the FastAPI server (uvicorn app.api.main:app --reload)'}
      </div>

      <div className="disclaimer">
        <strong>Research support only.</strong> This tool does not provide
        financial advice and is not an automated trading system. All output
        should be treated as a starting point for your own due diligence —
        not as a recommendation to buy, sell, or hold any security.
      </div>

      <div className="dashboard-actions">
        <Link to="/analyze" className="btn btn-primary">
          Analyze a ticker →
        </Link>
        <Link to="/reports" className="btn btn-secondary">
          View saved reports
        </Link>
      </div>
    </div>
  )
}
