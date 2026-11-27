import type { AverageSeriesPoint, Granularity, HouseholdSeries } from '../api/types'
import { PALETTE } from '../data/constants'
import { axisValue, formatPeriodShort } from './format'

export interface ChartPoint {
  x: number
  y: number
  value: number
  index: number
}

export interface ChartSeries {
  household_id: number
  display_name: string
  color: string
  values: Array<number | null>
  paths: string[]
  lastPoint: ChartPoint | null
}

export interface ChartGeometry {
  width: number
  height: number
  pad: { top: number; right: number; bottom: number; left: number }
  plotWidth: number
  plotHeight: number
  yMin: number
  yMax: number
  periods: string[]
  avgValues: Array<number | null>
  series: ChartSeries[]
  yTicks: Array<{ value: number; y: number; label: string }>
  xTicks: Array<{ index: number; x: number; label: string }>
  avgPaths: string[]
  avgAreas: string[]
  peakPoint: { x: number; y: number; period: string; value: number } | null
  axisUnit: string
  hoverX: number
}

function smoothPath(points: ChartPoint[]): string {
  if (!points.length) return ''
  if (points.length === 1) {
    return `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)} L ${(points[0].x + 0.6).toFixed(2)} ${points[0].y.toFixed(2)}`
  }

  let path = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`
  for (let index = 0; index < points.length - 1; index += 1) {
    const p0 = points[index - 1] || points[index]
    const p1 = points[index]
    const p2 = points[index + 1]
    const p3 = points[index + 2] || p2
    const cp1x = p1.x + (p2.x - p0.x) / 6
    const cp1y = p1.y + (p2.y - p0.y) / 6
    const cp2x = p2.x - (p3.x - p1.x) / 6
    const cp2y = p2.y - (p3.y - p1.y) / 6
    path += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`
  }
  return path
}

function tickIndexes(count: number): number[] {
  if (count <= 7) return Array.from({ length: count }, (_, index) => index)
  if (count <= 12) {
    const ticks: number[] = []
    for (let index = 0; index < count; index += 2) ticks.push(index)
    if (ticks[ticks.length - 1] !== count - 1) ticks.push(count - 1)
    return ticks
  }
  return [0, 5, 10, 15, 20, 25, count - 1].filter(
    (index, position, array) => index < count && array.indexOf(index) === position
  )
}

function splitPointRuns(values: Array<number | null>): ChartPoint[][] {
  const runs: ChartPoint[][] = []
  let current: ChartPoint[] = []
  values.forEach((value, index) => {
    if (value === null || !Number.isFinite(value)) {
      if (current.length) runs.push(current)
      current = []
      return
    }
    current.push({ x: index, y: index, value, index })
  })
  if (current.length) runs.push(current)
  return runs
}

export function buildChart(
  seriesData: HouseholdSeries[],
  averageData: AverageSeriesPoint[],
  granularity: Granularity,
  hoverIndex: number | null,
  _hoverPercent: number
): ChartGeometry {
  const width = 920
  const height = 320
  const pad = { top: 24, right: 16, bottom: 34, left: 44 }
  const plotWidth = width - pad.left - pad.right
  const plotHeight = height - pad.top - pad.bottom
  const periodSet = new Set<string>()
  seriesData.forEach((series) => series.points.forEach((point) => periodSet.add(point.period)))
  averageData.forEach((point) => periodSet.add(point.period))
  const periods = Array.from(periodSet).sort()

  if (!periods.length) {
    return {
      width,
      height,
      pad,
      plotWidth,
      plotHeight,
      yMin: 0,
      yMax: 1,
      periods,
      avgValues: [],
      series: [],
      yTicks: [],
      xTicks: [],
      avgPaths: [],
      avgAreas: [],
      peakPoint: null,
      axisUnit: granularity === 'month' ? 'KWH / MONTH' : 'KWH / DAY',
      hoverX: 0
    }
  }

  const avgMap = new Map(averageData.map((point) => [point.period, point.avg_kwh]))
  const rawSeries = seriesData.map((series, index) => {
    const pointMap = new Map(series.points.map((point) => [point.period, point.kwh]))
    return {
      ...series,
      color: PALETTE[(series.color_index == null ? index : series.color_index) % PALETTE.length],
      values: periods.map((period) => {
        const value = pointMap.get(period)
        return value === null || value === undefined || !Number.isFinite(value) ? null : value
      })
    }
  })
  const avgValues = periods.map((period) => {
    if (avgMap.has(period)) return avgMap.get(period) ?? null
    const values = rawSeries
      .map((series) => series.values[periods.indexOf(period)])
      .filter((value): value is number => value !== null && Number.isFinite(value))
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
  })
  const allValues = rawSeries
    .flatMap((series) => series.values)
    .concat(avgValues)
    .filter((value): value is number => value !== null && Number.isFinite(value))
  const rawMin = allValues.length ? Math.min(...allValues) : 0
  const rawMax = allValues.length ? Math.max(...allValues) : 1
  const span = Math.max(rawMax - rawMin, granularity === 'month' ? 8 : 0.6)
  const lower = Math.max(0, rawMin - span * 0.18)
  const upper = rawMax + span * 0.22
  const yMin = Number(lower.toFixed(1))
  const yMax = Number(upper.toFixed(1))
  const xAt = (index: number) => pad.left + (plotWidth * index) / Math.max(1, periods.length - 1)
  const yAt = (value: number) => pad.top + plotHeight - ((value - yMin) / Math.max(0.001, yMax - yMin)) * plotHeight

  const buildPaths = (values: Array<number | null>): string[] =>
    splitPointRuns(values).map((run) =>
      smoothPath(run.map((point) => ({ ...point, x: xAt(point.index), y: yAt(point.value) })))
    )

  const series = rawSeries.map((item) => {
    const numericPoints = item.values
      .map((value, index) =>
        value === null ? null : { x: xAt(index), y: yAt(value), index, value }
      )
      .filter((point): point is ChartPoint => point !== null)
    return {
      household_id: item.household_id,
      display_name: item.display_name,
      color: item.color,
      values: item.values,
      paths: buildPaths(item.values),
      lastPoint: numericPoints.length ? numericPoints[numericPoints.length - 1] : null
    }
  })

  const bottomY = pad.top + plotHeight
  const avgRuns = splitPointRuns(avgValues).map((run) =>
    run.map((point) => ({ ...point, x: xAt(point.index), y: yAt(point.value) }))
  )
  const avgPaths = avgRuns.map((run) => smoothPath(run))
  const avgAreas = avgRuns
    .filter((run) => run.length > 1)
    .map((run) => {
      const line = run.map((point) => `${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' L ')
      return `M ${run[0].x.toFixed(2)} ${bottomY} L ${line} L ${run[run.length - 1].x.toFixed(2)} ${bottomY} Z`
    })

  const yTicks = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3
    const value = yMax - (yMax - yMin) * ratio
    return {
      value: Number(value.toFixed(1)),
      y: pad.top + plotHeight * ratio,
      label: axisValue(value)
    }
  })

  const maxIndex = avgValues.reduce<number>((best, value, index) => {
    if (value === null) return best
    if (best === -1) return index
    return value > (avgValues[best] ?? -Infinity) ? index : best
  }, -1)
  const peakPoint =
    maxIndex >= 0
      ? {
          x: xAt(maxIndex),
          y: yAt(avgValues[maxIndex] ?? 0),
          period: periods[maxIndex],
          value: avgValues[maxIndex] ?? 0
        }
      : null

  return {
    width,
    height,
    pad,
    plotWidth,
    plotHeight,
    yMin,
    yMax,
    periods,
    avgValues,
    series,
    yTicks,
    xTicks: tickIndexes(periods.length).map((index) => ({
      index,
      x: xAt(index),
      label: formatPeriodShort(periods[index])
    })),
    avgPaths,
    avgAreas,
    peakPoint,
    axisUnit: granularity === 'month' ? 'KWH / MONTH' : 'KWH / DAY',
    hoverX: hoverIndex === null ? 0 : xAt(hoverIndex)
  }
}
