import { useEffect, useRef } from 'react'
import { AreaSeries, ColorType, createChart } from 'lightweight-charts'
import { toClosingLineData } from '../../lib/chartData'
import type { PricePoint } from '../../types/marketData'

interface StockPriceChartProps {
  prices: PricePoint[]
  height?: number
}

const DEFAULT_HEIGHT = 320

/**
 * Daily closing-price area chart (Lightweight Charts), themed for the dark
 * dashboard. The chart instance is created on mount and removed on unmount to
 * avoid leaks; it resizes to its container width via a ResizeObserver.
 */
export function StockPriceChart({
  prices,
  height = DEFAULT_HEIGHT,
}: StockPriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
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
      timeScale: { borderColor: '#232c3b' },
    })

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#4f8cff',
      lineWidth: 2,
      topColor: 'rgba(79, 140, 255, 0.35)',
      bottomColor: 'rgba(79, 140, 255, 0.02)',
      priceLineVisible: false,
    })
    series.setData(toClosingLineData(prices))
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
  }, [prices, height])

  return <div ref={containerRef} className="price-chart" />
}
