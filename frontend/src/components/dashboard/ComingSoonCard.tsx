import type { ReactNode } from 'react'

interface ComingSoonCardProps {
  title: string
  description: string
  /** Optional inert preview content (e.g. labeled placeholder rows). */
  children?: ReactNode
  /** Span the full grid width when true. */
  wide?: boolean
}

/**
 * A dashboard card for features that are planned but not built/connected yet.
 * Always renders an explicit "Coming Soon" badge so a placeholder can never be
 * mistaken for live data (see docs/ui_dashboard_vision.md §8).
 */
export function ComingSoonCard({
  title,
  description,
  children,
  wide = false,
}: ComingSoonCardProps) {
  return (
    <section
      className={`dashboard-card coming-soon-card${
        wide ? ' dashboard-card--wide' : ''
      }`}
      aria-label={`${title} (coming soon)`}
    >
      <div className="dashboard-card-head">
        <h2 className="dashboard-card-title">{title}</h2>
        <span className="coming-soon-badge">Coming Soon</span>
      </div>
      <p className="dashboard-card-note">{description}</p>
      {children}
    </section>
  )
}
