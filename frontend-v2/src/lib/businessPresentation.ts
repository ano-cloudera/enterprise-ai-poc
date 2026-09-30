const labelOverrides: Record<string, string> = {
  calmonth: 'Calendar Month',
  metric_value: 'Metric Value',
  sales_off: 'Sales Office',
  dcname: 'Distribution Center',
}

export function formatBusinessLabel(value: string): string {
  const normalized = value.trim().toLowerCase()
  if (labelOverrides[normalized]) return labelOverrides[normalized]
  return value.replaceAll('_', ' ').replaceAll('-', ' ').replace(/\b\w/g, character => character.toUpperCase())
}

export function formatBusinessValue(field: string, value: unknown, metric?: string, unitFormat?: string | null): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value !== 'number') return String(value)
  if (!Number.isFinite(value)) return 'Unavailable'
  if (unitFormat === 'percent') return `${value.toFixed(1)}%`
  if (unitFormat === 'quantity' || unitFormat === 'count') return Math.round(value).toLocaleString('en-US')
  if (unitFormat === 'ratio') return value.toFixed(2)
  if (unitFormat === 'minutes') return `${value.toLocaleString('en-US', { maximumFractionDigits: 1 })} min`
  if (unitFormat === 'currency_idr' || /(sales|revenue|value|amount)/i.test(`${field} ${metric || ''}`)) {
    const absolute = Math.abs(value)
    const sign = value < 0 ? '-' : ''
    if (absolute >= 1_000_000_000_000) return `${sign}Rp${(absolute / 1_000_000_000_000).toFixed(2)}T`
    if (absolute >= 1_000_000_000) return `${sign}Rp${(absolute / 1_000_000_000).toFixed(2)}B`
    if (absolute >= 1_000_000) return `${sign}Rp${(absolute / 1_000_000).toFixed(1)}M`
    return `${sign}Rp${absolute.toLocaleString('id-ID', { maximumFractionDigits: 2 })}`
  }
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}
