import type { AppliedContextItem, DashboardState, UIAction } from '../types/api'

const filterKeys = ['region', 'product', 'category', 'channel', 'outlet', 'customer_segment']

export const initialDashboardState: DashboardState = {
  filters: Object.fromEntries(filterKeys.map(key => [key, []])),
  date_range: { preset: 'current_month', start: null, end: null },
  metric: 'net_sales',
  dimension: 'region',
  highlights: [],
  ai_applied_context: [],
  revision: 0,
  chat: { chart: null, table: { visible: false, columns: [] } },
}

function contextWithout(items: AppliedContextItem[], kind: AppliedContextItem['kind'], target: string) {
  return items.filter(item => item.kind !== kind || item.target !== target)
}

function withContext(state: DashboardState, item: AppliedContextItem) {
  return [...contextWithout(state.ai_applied_context, item.kind, item.target), item]
}

export function applyUiAction(state: DashboardState, candidate: UIAction | unknown): DashboardState {
  if (!candidate || typeof candidate !== 'object' || !("type" in candidate)) return state
  const action = candidate as UIAction
  switch (action.type) {
    case 'SET_FILTER':
      if (typeof action.target !== 'string' || !filterKeys.includes(action.target) || !Array.isArray(action.value) || !action.value.every(value => typeof value === 'string')) return state
      return { ...state, filters: { ...state.filters, [action.target]: action.value.map(String) }, ai_applied_context: withContext(state, { kind: 'filter', target: action.target, label: action.value.join(', ') }), revision: state.revision + 1 }
    case 'SET_DATE_RANGE': {
      if (typeof action.value !== 'string' && (!action.value || typeof action.value !== 'object' || typeof action.value.start !== 'string' || typeof action.value.end !== 'string')) return state
      const dateRange = typeof action.value === 'string'
        ? { preset: action.value, start: null, end: null }
        : { preset: null, start: action.value.start, end: action.value.end }
      const label = typeof action.value === 'string' ? action.value.replaceAll('_', ' ') : `${action.value.start} – ${action.value.end}`
      return { ...state, date_range: dateRange, ai_applied_context: withContext(state, { kind: 'date_range', target: 'date_range', label }), revision: state.revision + 1 }
    }
    case 'CHANGE_METRIC':
      return typeof action.value === 'string' ? { ...state, metric: action.value, revision: state.revision + 1 } : state
    case 'CHANGE_DIMENSION':
      return typeof action.value === 'string' ? { ...state, dimension: action.value, revision: state.revision + 1 } : state
    case 'HIGHLIGHT_CARD': {
      if (typeof action.target !== 'string' || (typeof action.value !== 'string' && !Array.isArray(action.value))) return state
      const values = Array.isArray(action.value) ? action.value : [action.value]
      return { ...state, highlights: values.filter(Boolean).map(value => ({ target: action.target, value: String(value) })), revision: state.revision + 1 }
    }
    case 'RENDER_CHART':
      return action.value && typeof action.value === 'object' && typeof action.value.chart_type === 'string' && typeof action.value.dimension === 'string' && typeof action.value.metric === 'string' ? { ...state, chat: { ...state.chat, chart: action.value }, revision: state.revision + 1 } : state
    case 'SHOW_TABLE':
      return action.value && Array.isArray(action.value.columns) ? { ...state, chat: { ...state.chat, table: { visible: true, columns: action.value.columns } }, revision: state.revision + 1 } : state
    case 'RESET_FILTER':
      if (action.target && typeof action.target === 'string' && filterKeys.includes(action.target)) {
        return {
          ...state,
          filters: { ...state.filters, [action.target]: [] },
          highlights: state.highlights.filter(item => item.target !== action.target),
          ai_applied_context: contextWithout(state.ai_applied_context, 'filter', action.target),
          revision: state.revision + 1,
        }
      }
      return { ...initialDashboardState, revision: state.revision + 1 }
    default:
      return state
  }
}

export function applyUiActions(state: DashboardState, actions: readonly unknown[]): DashboardState {
  return actions.reduce(applyUiAction, state)
}

export function removeAppliedContext(state: DashboardState, kind: AppliedContextItem['kind'], target: string): DashboardState {
  if (kind === 'filter') return applyUiAction(state, { type: 'RESET_FILTER', target })
  return {
    ...state,
    date_range: { preset: null, start: null, end: null },
    ai_applied_context: contextWithout(state.ai_applied_context, kind, target),
    revision: state.revision + 1,
  }
}
