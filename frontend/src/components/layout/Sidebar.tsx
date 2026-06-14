import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { checkHealth } from '../../api/analysisApi'

/**
 * Primary navigation. Portfolio is intentionally absent — it stays hidden
 * until manual holdings are actually implemented (see docs/ui_dashboard_vision.md).
 */
const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/analyze', label: 'Analyze', end: false },
  { to: '/watchlists', label: 'Watchlists', end: false },
  { to: '/reports', label: 'Reports', end: false },
]

type HealthStatus = 'checking' | 'ok' | 'unavailable'

const STATUS_LABEL: Record<HealthStatus, string> = {
  checking: 'Checking…',
  ok: 'Connected',
  unavailable: 'Offline',
}

export function Sidebar() {
  const [status, setStatus] = useState<HealthStatus>('checking')

  useEffect(() => {
    let active = true
    checkHealth()
      .then(() => {
        if (active) setStatus('ok')
      })
      .catch(() => {
        if (active) setStatus('unavailable')
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <aside className="app-sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark" aria-hidden="true">
          IB
        </span>
        <span className="sidebar-brand-text">
          <span className="sidebar-brand-name">Investment Bot</span>
          <span className="sidebar-brand-tag">Research dashboard</span>
        </span>
      </div>

      <nav className="sidebar-nav" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className="sidebar-link"
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div
          className={`data-status data-status-${status}`}
          role="status"
          aria-live="polite"
        >
          <span className="data-status-dot" aria-hidden="true" />
          <span className="data-status-label">Data: {STATUS_LABEL[status]}</span>
        </div>
      </div>
    </aside>
  )
}
