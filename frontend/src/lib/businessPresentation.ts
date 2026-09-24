import type { DashboardState } from '../types/api'

type ContextState = Pick<DashboardState, 'filters' | 'date_range' | 'metric'>

const labelOverrides: Record<string, string> = {
  current_month: 'Current Month',
  previous_month: 'Previous Month',
  last_3_months: 'Last 3 Months',
  last_6_months: 'Last 6 Months',
  year_to_date: 'Year to Date',
  net_sales: 'Net Sales',
  gross_sales: 'Gross Sales',
  sales_volume: 'Sales Volume',
  general_trade: 'General Trade',
  modern_trade: 'Modern Trade',
}

export function formatBusinessLabel(value: string): string {
  const normalized = value.trim().toLowerCase()
  if (labelOverrides[normalized]) return labelOverrides[normalized]
  return value
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\b\w/g, character => character.toUpperCase())
}

// Governed metrics (OSSIE/Impala) declare their own unit_format
// (currency_idr/quantity/percent/ratio/minutes/count) in tempo_core.ossie.yaml
// - when present, it is authoritative and skips the field/metric-name
// heuristics below entirely. Those heuristics remain as a fallback only for
// non-governed domains (forecast/weather/market) that don't carry a
// unit_format yet, since the generic SQL column name "metric_value" used
// for every governed metric previously made "value" in that name match the
// currency regex for ANY metric, including quantity/percent ones.
function formatByUnit(unitFormat: string, value: number): string | null {
  switch (unitFormat) {
    case 'currency_idr':
      return formatMillionIdr(value)
    case 'percent':
      return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
    case 'quantity':
    case 'count':
      return Math.round(value).toLocaleString('en-US')
    case 'ratio':
      return value.toFixed(2)
    case 'minutes':
      return `${value.toLocaleString('en-US', { maximumFractionDigits: 1 })} min`
    default:
      return null
  }
}

export function formatBusinessValue(field: string, value: unknown, metric?: string, unitFormat?: string | null): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value !== 'number') return String(value)
  if (!Number.isFinite(value)) return 'Unavailable'

  if (unitFormat) {
    const formatted = formatByUnit(unitFormat, value)
    if (formatted !== null) return formatted
  }

  const key = field.toLowerCase()
  const metricKey = metric?.toLowerCase() ?? ''
  if (/(percentage|percent|_pct|growth|share|change_rate)/.test(key)) return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
  if (key.includes('correlation')) return value.toFixed(2)
  if (/(count|units|volume|days)$/.test(key) || key.startsWith('number_of_')) return Math.round(value).toLocaleString('en-US')
  if (/(score|index)$/.test(key)) return value.toFixed(1)
  if (isMonetaryField(key, metricKey)) return formatMillionIdr(value)
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

export function businessContextItems(state: ContextState): { label: string; value: string }[] {
  const period = state.date_range.start && state.date_range.end
    ? `${state.date_range.start} – ${state.date_range.end}`
    : formatBusinessLabel(state.date_range.preset || 'All Time')

  return [
    { label: 'Period', value: period },
    { label: 'Region', value: selectedValues(state.filters.region, 'All Regions') },
    { label: 'Product', value: selectedValues(state.filters.product, 'All Products') },
    { label: 'Channel', value: selectedValues(state.filters.channel, 'All Channels') },
    { label: 'Metric', value: formatBusinessLabel(state.metric) },
  ]
}

export function suggestedFollowUps(intent: string): string[] {
  const normalized = intent.toLowerCase()
  if (normalized.includes('market') || normalized.includes('compet')) return [
    'Which region has the highest opportunity?',
    'Compare Bodrex with key competitors',
    'Where is the largest distribution gap?',
  ]
  if (normalized.includes('forecast')) return [
    'What are the main forecast drivers?',
    'Compare forecast with current sales',
    'Which region has the strongest outlook?',
  ]
  if (normalized.includes('weather')) return [
    'Which regions are most affected by weather?',
    'How does rainfall relate to sales?',
    'Compare weather impact by product',
  ]
  return [
    'Which products drove the decline?',
    'Which channel contributed most?',
    'Compare with the previous 3 months',
  ]
}

function selectedValues(values: string[] | undefined, fallback: string): string {
  if (!values?.length) return fallback
  return values.map(formatBusinessLabel).join(', ')
}

function isMonetaryField(field: string, metric: string): boolean {
  return /(sales|revenue|price|value|amount|absolute_change)/.test(field) || /(sales|revenue|price|amount)/.test(metric)
}

function formatMillionIdr(value: number): string {
  const sign = value < 0 ? '-' : ''
  const absolute = Math.abs(value)
  if (absolute >= 1_000_000) return `${sign}Rp${(absolute / 1_000_000).toFixed(2)}T`
  if (absolute >= 1_000) return `${sign}Rp${(absolute / 1_000).toFixed(2)}B`
  return `${sign}Rp${absolute.toFixed(2)}M`
}
