import type { UIAction } from '../types/api'

const automaticFilterTargets = new Set(['region', 'product', 'channel'])
const confirmationTypes = new Set(['CHANGE_METRIC', 'CHANGE_DIMENSION', 'RENDER_CHART', 'SHOW_TABLE', 'HIGHLIGHT_CARD'])
const chartTypes = new Set(['line', 'bar', 'area', 'pie', 'table'])
const renderTargets = new Set(['chat', 'dashboard', 'both'])
const sectionIds = {
  trend: 'sales-performance',
  region: 'sales-by-region',
  product: 'product-performance',
  channel: 'channel-contribution',
  market: 'market-signals',
} as const

export type DashboardTopic = keyof typeof sectionIds

export type DashboardAiActionPartition = {
  automatic: UIAction[]
  confirmationRequired: UIAction[]
  rejected: unknown[]
}

export function partitionDashboardAiActions(candidates: readonly unknown[]): DashboardAiActionPartition {
  return candidates.reduce<DashboardAiActionPartition>((result, candidate) => {
    if (isAutomaticAction(candidate)) result.automatic.push(candidate)
    else if (isConfirmationAction(candidate)) result.confirmationRequired.push(candidate)
    else result.rejected.push(candidate)
    return result
  }, { automatic: [], confirmationRequired: [], rejected: [] })
}

function isAutomaticAction(candidate: unknown): candidate is UIAction {
  if (!isRecord(candidate) || typeof candidate.type !== 'string') return false
  if (candidate.type === 'SET_FILTER') {
    return typeof candidate.target === 'string'
      && automaticFilterTargets.has(candidate.target)
      && Array.isArray(candidate.value)
      && candidate.value.length > 0
      && candidate.value.every(value => typeof value === 'string')
  }
  if (candidate.type !== 'SET_DATE_RANGE') return false
  if (typeof candidate.value === 'string') return Boolean(candidate.value)
  return isRecord(candidate.value)
    && typeof candidate.value.start === 'string'
    && typeof candidate.value.end === 'string'
}

function isConfirmationAction(candidate: unknown): candidate is UIAction {
  if (!isRecord(candidate) || typeof candidate.type !== 'string' || !confirmationTypes.has(candidate.type)) return false
  if (candidate.type === 'CHANGE_METRIC' || candidate.type === 'CHANGE_DIMENSION') return typeof candidate.value === 'string' && Boolean(candidate.value)
  if (candidate.type === 'HIGHLIGHT_CARD') {
    return typeof candidate.target === 'string'
      && (typeof candidate.value === 'string' || (Array.isArray(candidate.value) && candidate.value.every(value => typeof value === 'string')))
  }
  if (!renderTargets.has(String(candidate.target)) || !isRecord(candidate.value)) return false
  if (candidate.type === 'SHOW_TABLE') return Array.isArray(candidate.value.columns) && candidate.value.columns.every(column => typeof column === 'string')
  return chartTypes.has(String(candidate.value.chart_type))
    && typeof candidate.value.dimension === 'string'
    && typeof candidate.value.metric === 'string'
}

export function actionLabel(action: UIAction): string {
  switch (action.type) {
    case 'CHANGE_METRIC': return `View ${humanize(action.value)}`
    case 'SHOW_TABLE': return 'View supporting data'
    case 'HIGHLIGHT_CARD': {
      const value = Array.isArray(action.value) ? action.value[0] : action.value
      return value && !['growth', 'forecast', 'opportunity'].includes(value) ? `Focus on ${value}` : labelForTopic(topicForAction(action))
    }
    default: return labelForTopic(topicForAction(action))
  }
}

export function dashboardSectionForAction(action: UIAction): string {
  return dashboardSectionForTopic(topicForAction(action))
}

export function dashboardSectionForTopic(topic: DashboardTopic): string {
  return sectionIds[topic]
}

export function selectDashboardActions(actions: readonly UIAction[]): UIAction[] {
  const selected: UIAction[] = []
  const sections = new Set<string>()
  const prioritized = actions.map((action, index) => ({ action, index })).sort((left, right) => actionPriority(left.action) - actionPriority(right.action) || left.index - right.index)
  for (const { action } of prioritized) {
    const section = dashboardSectionForAction(action)
    if (sections.has(section)) continue
    selected.push(action)
    sections.add(section)
    if (selected.length === 2) break
  }
  return selected
}

function actionPriority(action: UIAction): number {
  switch (action.type) {
    case 'CHANGE_DIMENSION': return 0
    case 'HIGHLIGHT_CARD': return 1
    case 'RENDER_CHART': return 2
    case 'SHOW_TABLE': return 3
    case 'CHANGE_METRIC': return 4
    default: return 5
  }
}

function topicForAction(action: UIAction): DashboardTopic {
  if (action.type === 'CHANGE_DIMENSION') return topicFromValue(action.value)
  if (action.type === 'RENDER_CHART') return topicFromValue(action.value.dimension)
  if (action.type === 'SHOW_TABLE') return topicFromValue(action.value.columns.join(' '))
  if (action.type === 'HIGHLIGHT_CARD') return topicFromValue(`${action.target} ${Array.isArray(action.value) ? action.value.join(' ') : action.value}`)
  return 'trend'
}

function topicFromValue(value: string): DashboardTopic {
  const normalized = value.toLowerCase()
  if (normalized.includes('market') || normalized.includes('opportunity')) return 'market'
  if (normalized.includes('channel')) return 'channel'
  if (normalized.includes('product')) return 'product'
  if (normalized.includes('region')) return 'region'
  return 'trend'
}

function labelForTopic(topic: DashboardTopic): string {
  return {
    trend: 'View sales trend',
    region: 'Compare regions',
    product: 'View product drivers',
    channel: 'Compare channels',
    market: 'Review market opportunity',
  }[topic]
}

function humanize(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}
