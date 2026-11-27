import type { BreakdownItem } from '../api/types'
import { APPLIANCE_COLORS, APPLIANCE_NAMES } from '../data/constants'

export interface MixItem extends BreakdownItem {
  name: string
  color: string
  percent: number
}

export function applianceMix(breakdown: BreakdownItem[]): {
  items: MixItem[]
  total: number
  legend: Array<{ name: string; color: string; percent: string }>
  gradient: string
} {
  const total = breakdown.reduce((sum, item) => sum + (item.kwh || 0), 0)
  const items = breakdown
    .slice()
    .sort((a, b) => (b.kwh || 0) - (a.kwh || 0))
    .map((item, index) => ({
      ...item,
      name: APPLIANCE_NAMES[item.appliance_name] || item.appliance_name,
      color: APPLIANCE_COLORS[index % APPLIANCE_COLORS.length],
      percent: ((item.kwh || 0) / Math.max(total, 0.001)) * 100
    }))

  const baseLegend =
    items.length <= 5
      ? items.map((item) => ({
          name: item.name,
          color: item.color,
          percent: item.percent.toFixed(0)
        }))
      : items.slice(0, 5).map((item) => ({
          name: item.name,
          color: item.color,
          percent: item.percent.toFixed(0)
        }))

  if (items.length > 5) {
    const restKwh = items.slice(5).reduce((sum, item) => sum + item.kwh, 0)
    baseLegend.push({
      name: '其他',
      color: '#8e8e93',
      percent: ((restKwh / Math.max(total, 0.001)) * 100).toFixed(0)
    })
  }

  let current = 0
  const segments = baseLegend.map((item) => {
    const start = current
    current += Number(item.percent)
    return `${item.color} ${start}% ${current}%`
  })
  const remainder = Math.max(0, 100 - current)
  if (remainder > 0.2) segments.push(`#edf0f5 ${current}% 100%`)

  return {
    items,
    total,
    legend: baseLegend,
    gradient: `conic-gradient(${segments.join(',')})`
  }
}
