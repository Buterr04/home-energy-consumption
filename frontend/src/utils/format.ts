export function pad(value: number | string): string {
  return String(value).padStart(2, '0')
}

export function parseDate(dateString: string): Date {
  const parts = String(dateString).split('-').map(Number)
  return new Date(Date.UTC(parts[0], (parts[1] || 1) - 1, parts[2] || 1))
}

export function isoDate(date: Date): string {
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`
}

export function addDays(dateString: string, delta: number): string {
  const date = parseDate(dateString)
  date.setUTCDate(date.getUTCDate() + delta)
  return isoDate(date)
}

export function periodYear(period: string): string {
  return String(period || '').slice(0, 4)
}

export function formatPeriodShort(period: string): string {
  if (!period) return ''
  if (period.length === 7) return `${Number(period.slice(5, 7))}月`
  if (period.length === 4) return period
  return `${Number(period.slice(5, 7))}/${Number(period.slice(8, 10))}`
}

export function formatPeriodCn(period: string): string {
  if (!period) return ''
  if (period.length === 7) return `${period.slice(0, 4)}年${Number(period.slice(5, 7))}月`
  if (period.length === 4) return `${period}年`
  return `${period.slice(0, 4)}年${Number(period.slice(5, 7))}月${Number(period.slice(8, 10))}日`
}

export function formatKwh(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—'
  const number = Number(value)
  return number >= 100 ? number.toFixed(0) : number.toFixed(2)
}

export function formatCompact(value: number | null | undefined): string {
  const number = Number(value) || 0
  if (number >= 1000) return `${(number / 1000).toFixed(1)}k`
  return number.toFixed(number >= 100 ? 0 : 1)
}

export function formatNumber(value: number | null | undefined): string {
  return Number(value || 0).toLocaleString('zh-CN')
}

export function formatPeople(value: number | null | undefined): string {
  if (value == null) return '— 人'
  return `${Number(value).toFixed(Number(value) % 1 === 0 ? 0 : 1)} 人`
}

export function formatTemp(value: number | null | undefined): string {
  return value == null ? '— °C' : `${Number(value).toFixed(1)} °C`
}

export function axisValue(value: number): string {
  if (Math.abs(value) >= 100) return Number(value).toFixed(0)
  return Number(value).toFixed(1)
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
