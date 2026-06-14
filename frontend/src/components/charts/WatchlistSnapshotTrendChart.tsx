import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ColorType,
  LineSeries,
  createChart,
  type UTCTimestamp,
} from 'lightweight-charts'
import {
  toSnapshotAverageScoreTrendData,
  toSnapshotSuccessTrendData,
} from '../../lib/snapshotTrend'
import type { WatchlistSnapshotSummary } from '../../types/watchlist'

interface WatchlistSnapshotTrendChartProps {
  snapshots: readonly WatchlistSnapshotSummary[]
  height?: number
}

type TrendMetric = 'success' | 'average'

interface MetricConfig {
  label: string
  caption: string
  color: string
  emptyMessage: string
}

const METRICS: Record<TrendMetric, MetricConfig> = {
  success: {
    label: 'Success count',
    caption: 'Successful ticker count from saved snapshots.',
    color: '#3fb98a',
    emptyMessage: 'Save at least two snapshots to see a trend.',
  },
  average: {
    label: 'Average score',
    caption: 'Average score from saved successful ticker results.',
    color: '#4f8cff',
    emptyMessage:
      'Save at least two snapshots with successful results to see an average-score trend.',
  },
}

const DEFAULT_HEIGHT = 240
const MIN_POINTS = 2

/**
 * Trend chart for saved watchlist snapshots (Lightweight Charts), themed for the
 * dark dashboard. A toggle switches between two single-line views — successful
 * ticker count and backend-derived average score — so the two units never share
 * an axis. It plots only values already saved on each snapshot summary: no new
 * fetches, no analysis, no average computed in the frontend. Historical data
 * only; it never refreshes on its own.
 *
 * The chart instance is created on mount/update and removed on unmount; it
 * resizes to its container width via a ResizeObserver, mirroring StockPriceChart.
 */
export function WatchlistSnapshotTrendChart({
  snapshots,
  height = DEFAULT_HEIGHT,
}: WatchlistSnapshotTrendChartProps) {
  const [metric, setMetric] = useState<TrendMetric>('success')
  const containerRef = useRef<HTMLDivElement>(null)

  const data = useMemo(
    () =>
      metric === 'success'
        ? toSnapshotSuccessTrendData(snapshots)
        : toSnapshotAverageScoreTrendData(snapshots),
    [snapshots, metric],
  )

  const config = METRICS[metric]
  const hasTrend = data.length >= MIN_POINTS

  useEffect(() => {
    if (!hasTrend) return
    const el = containerRef.current
    if (!el) return

    const chart = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#8b95a6',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: 'rgba(35, 44, 59, 0.5)' },
        horzLines: { color: 'rgba(35, 44, 59, 0.5)' },
      },
      rightPriceScale: { borderColor: '#232c3b' },
      timeScale: {
        borderColor: '#232c3b',
        timeVisible: true,
        secondsVisible: false,
      },
    })

    const series = chart.addSeries(LineSeries, {
      color: config.color,
      lineWidth: 2,
      priceLineVisible: false,
      pointMarkersVisible: true,
    })
    series.setData(
      data.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })),
    )
    chart.timeScale().fitContent()

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width
      if (width) chart.applyOptions({ width: Math.floor(width) })
    })
    observer.observe(el)

    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [data, hasTrend, height, config.color])

  return (
    <div className="snapshot-trend">
      <div
        className="snapshot-trend-toggle"
        role="group"
        aria-label="Trend metric"
      >
        {(Object.keys(METRICS) as TrendMetric[]).map((key) => (
          <button
            key={key}
            type="button"
            className="snapshot-trend-toggle-btn"
            aria-pressed={metric === key}
            onClick={() => setMetric(key)}
          >
            {METRICS[key].label}
          </button>
        ))}
      </div>

      <p className="snapshot-trend-caption">{config.caption}</p>

      {hasTrend ? (
        <div ref={containerRef} className="snapshot-trend-chart" />
      ) : (
        <p className="empty-state">{config.emptyMessage}</p>
      )}
    </div>
  )
}
