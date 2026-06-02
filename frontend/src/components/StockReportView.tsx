import type { ReactNode } from 'react'
import type { StockReport } from '../types/report'

interface Props {
  report: StockReport
  /** ID of the saved snapshot, shown when report was saved via analyze-and-save. */
  savedId?: number
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="report-section">
      <h3 className="section-title">{title}</h3>
      {children}
    </section>
  )
}

export function StockReportView({ report, savedId }: Props) {
  const hasSummaries =
    report.technical_summary ||
    report.fundamental_summary ||
    report.news_summary ||
    report.risk_summary

  const hasTriggers = report.buy_trigger || report.sell_or_avoid_trigger

  return (
    <div className="report-view">
      <div className="report-header">
        <div className="report-identity">
          <h2 className="report-ticker">{report.ticker}</h2>
          {report.company_name && (
            <p className="report-company">{report.company_name}</p>
          )}
          {report.current_price != null && (
            <p className="report-price">${report.current_price.toFixed(2)}</p>
          )}
        </div>
        <div className="report-verdict">
          <span className="category-badge">{report.final_category}</span>
          <p className="report-score">Score: {report.score.toFixed(1)}</p>
          <p className="report-confidence">
            Confidence: {report.confidence_level}
          </p>
        </div>
      </div>

      {savedId != null && (
        <p className="saved-notice">Saved to history — report ID #{savedId}</p>
      )}

      {hasSummaries && (
        <Section title="Analysis Summaries">
          {report.technical_summary && (
            <p>
              <strong>Technical:</strong> {report.technical_summary}
            </p>
          )}
          {report.fundamental_summary && (
            <p>
              <strong>Fundamental:</strong> {report.fundamental_summary}
            </p>
          )}
          {report.news_summary && (
            <p>
              <strong>News:</strong> {report.news_summary}
            </p>
          )}
          {report.risk_summary && (
            <p>
              <strong>Risk:</strong> {report.risk_summary}
            </p>
          )}
        </Section>
      )}

      {report.key_positive_factors.length > 0 && (
        <Section title="Key Positive Factors">
          <ul>
            {report.key_positive_factors.map((factor, i) => (
              <li key={i}>{factor}</li>
            ))}
          </ul>
        </Section>
      )}

      {report.key_risks.length > 0 && (
        <Section title="Key Risks">
          <ul>
            {report.key_risks.map((risk, i) => (
              <li key={i}>{risk}</li>
            ))}
          </ul>
        </Section>
      )}

      {hasTriggers && (
        <Section title="Action Triggers">
          {report.buy_trigger && (
            <p>
              <strong>Consider buying if:</strong> {report.buy_trigger}
            </p>
          )}
          {report.sell_or_avoid_trigger && (
            <p>
              <strong>Consider selling / avoiding if:</strong>{' '}
              {report.sell_or_avoid_trigger}
            </p>
          )}
        </Section>
      )}

      <Section title="Metadata">
        <p>Data as of: {formatTimestamp(report.data_timestamp)}</p>
        {report.data_sources_used.length > 0 && (
          <p>Sources: {report.data_sources_used.join(', ')}</p>
        )}
      </Section>
    </div>
  )
}
