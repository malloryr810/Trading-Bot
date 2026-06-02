/**
 * TypeScript interfaces that mirror the backend Pydantic schemas.
 * These are display-layer types only — no analysis or scoring logic lives here.
 *
 * Source of truth: app/models/stock_report.py, app/api/schemas/reports.py
 */

export interface StockReport {
  ticker: string
  company_name: string | null
  current_price: number | null
  final_category: string
  score: number
  confidence_level: string
  technical_summary: string | null
  fundamental_summary: string | null
  news_summary: string | null
  risk_summary: string | null
  key_positive_factors: string[]
  key_risks: string[]
  buy_trigger: string | null
  sell_or_avoid_trigger: string | null
  data_timestamp: string | null
  data_sources_used: string[]
}

export interface SavedReportSummary {
  id: number
  ticker: string
  company_name: string | null
  category: string
  score: number
  confidence: string
  created_at: string
}

export interface SavedReportDetail extends SavedReportSummary {
  report: StockReport
}
