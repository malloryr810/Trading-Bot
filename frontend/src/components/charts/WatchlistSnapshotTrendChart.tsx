import { useEffect, useMemo, useRef } from 'react'
import {
  ColorType,
  LineSeries,
  createChart,
  type UTCTimestamp,
} from 'lightweight-charts'
import { toSnapshotSuccessTrendData } from '../../lib/snapshotTrend'
import type { WatchlistSnapshotSummary } from '../../types/watchlist'

interface WatchlistSnapshotTrendChartProps {
  snapshots: readonly WatchlistSnapshotSummary[]
  height?: number
}

const DEFAULT_HEIGHT = 240
const MIN_POINTS = 2

/**
 * Line chart of successful-ticker count across saved watchlist snapshots
 * (Lightweight Charts), themed for the dark dashboard. It plots only the
 * `success_count` already saved on each snapshot summary — no new fetches, no
 * analysis. Historical data only; it never refreshes on its own.
 *
 * The chart instance is created on mount/update and removed on unmount; it
 * resizes to its container width via a ResizeObserver, mirroring StockPriceChart.
 */
export function WatchlistSnapshotTrendChart({
  snapshots,
  height = DEFAULT_HEIGHT,
}: WatchlistSnapshotTrendChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const data = useMemo(
    () => toSnapshotSuccessTrendData(snapshots),
    [snapshots],
  )

  useEffect(() => {
    if (data.length < MIN_POINTS) return
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
      color: '#3fb98a',
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
  }, [data, height])

  if (data.length < MIN_POINTS) {
    return (
      <p className="empty-state">
        Save at least two snapshots to see a trend.
      </p>
    )
  }

  return <div ref={containerRef} className="snapshot-trend-chart" />
}
