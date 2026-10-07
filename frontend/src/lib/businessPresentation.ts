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

/** Infer display unit from column name when API unit_format is absent. */
export function inferColumnUnitFormat(column: string, metric?: string): string | null {
  const col = column.trim().toLowerCase()
  const metricKey = (metric || '').toLowerCase()

  if (col === 'metric_value' && metricKey) {
    if (/fill_rate|service_fill|oos_rate/.test(metricKey)) return 'percent'
    if (/minutes|picking|unloading/.test(metricKey)) return 'minutes'
    if (/ratio|_to_|variance|months_of_stock|stock_cover|cover/.test(metricKey)) return 'ratio'
    if (/quantity|_qty|_count|stock_qty|unfulfilled|observation_count/.test(metricKey)) return 'quantity'
    if (
      /_value$|_val$|stock_value|billing|penagihan|revenue|gross|sell_in|sell_out|branch_sell/.test(metricKey)
    ) {
      return 'currency_idr'
    }
  }

  if (/contribution_pct|cumulative_pct|_pct$|_rate$|fill_rate|oos_rate/.test(col)) return 'percent'
  if (/_val$|bill_val|stock_val|sell_in_val|sell_out_val|billing|revenue|gross|amount/.test(col)) return 'currency_idr'
  if (/_qty$|quantity|unfulfilled|stock_qty|bill_qty|po_qty|do_qty/.test(col)) return 'quantity'
  if (/minutes|duration_min/.test(col)) return 'minutes'

  return null
}

export function formatBusinessValue(field: string, value: unknown, metric?: string, unitFormat?: string | null): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value !== 'number') return String(value)
  if (!Number.isFinite(value)) return 'Unavailable'

  const col = field.trim().toLowerCase()
  const resolvedUnit = unitFormat ?? (col === 'metric_value' ? inferColumnUnitFormat(field, metric) : inferColumnUnitFormat(field))

  if (resolvedUnit === 'percent') {
    const scaled = Math.abs(value) <= 1 && value !== 0 ? value * 100 : value
    return `${scaled.toFixed(1)}%`
  }
  if (resolvedUnit === 'quantity' || resolvedUnit === 'count') return Math.round(value).toLocaleString('en-US')
  if (resolvedUnit === 'ratio') return value.toFixed(2)
  if (resolvedUnit === 'minutes') return `${value.toLocaleString('en-US', { maximumFractionDigits: 1 })} min`
  if (resolvedUnit === 'currency_idr') {
    const absolute = Math.abs(value)
    const sign = value < 0 ? '-' : ''
    if (absolute >= 1_000_000_000_000) return `${sign}Rp${(absolute / 1_000_000_000_000).toFixed(2)}T`
    if (absolute >= 1_000_000_000) return `${sign}Rp${(absolute / 1_000_000_000).toFixed(2)}B`
    if (absolute >= 1_000_000) return `${sign}Rp${(absolute / 1_000_000).toFixed(1)}M`
    return `${sign}Rp${absolute.toLocaleString('id-ID', { maximumFractionDigits: 2 })}`
  }

  // Legacy column heuristics (never treat generic "metric_value" as currency via the word "value").
  if (
    col !== 'metric_value'
    && /(sales|revenue|amount)/i.test(`${field} ${metric || ''}`)
    && /_val$|bill_val|amount/.test(col)
  ) {
    const absolute = Math.abs(value)
    const sign = value < 0 ? '-' : ''
    if (absolute >= 1_000_000) return `${sign}Rp${(absolute / 1_000_000).toFixed(1)}M`
    return `${sign}Rp${absolute.toLocaleString('id-ID', { maximumFractionDigits: 2 })}`
  }

  return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}
