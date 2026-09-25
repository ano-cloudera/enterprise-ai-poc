import type { ChatResponse, UIAction } from '../types/api'

const targetPattern = /^[A-Za-z][A-Za-z0-9_.-]*$/
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const exactKeys = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).every(key => keys.includes(key))
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.length > 0 && value.every(item => typeof item === 'string' && item.length > 0)

function isAction(value: unknown): value is UIAction {
  if (!isRecord(value) || typeof value.type !== 'string') return false
  const validTarget = typeof value.target === 'string' && targetPattern.test(value.target)
  switch (value.type) {
    case 'SET_FILTER':
      return exactKeys(value, ['type', 'target', 'value']) && validTarget && strings(value.value)
    case 'HIGHLIGHT_CARD':
      return exactKeys(value, ['type', 'target', 'value']) && validTarget && ((typeof value.value === 'string' && value.value.length > 0) || strings(value.value))
    case 'SET_DATE_RANGE':
      return exactKeys(value, ['type', 'value']) && ((typeof value.value === 'string' && value.value.length > 0) || (isRecord(value.value) && exactKeys(value.value, ['start', 'end']) && typeof value.value.start === 'string' && value.value.start.length > 0 && typeof value.value.end === 'string' && value.value.end.length > 0))
    case 'CHANGE_METRIC':
    case 'CHANGE_DIMENSION':
      return exactKeys(value, ['type', 'value']) && typeof value.value === 'string' && targetPattern.test(value.value)
    case 'RENDER_CHART': {
      const chart = value.value
      return exactKeys(value, ['type', 'target', 'value']) && ['chat', 'dashboard', 'both'].includes(String(value.target)) && isRecord(chart) && exactKeys(chart, ['chart_type', 'dimension', 'metric']) && ['line', 'bar', 'area', 'pie', 'table'].includes(String(chart.chart_type)) && typeof chart.dimension === 'string' && targetPattern.test(chart.dimension) && typeof chart.metric === 'string' && targetPattern.test(chart.metric)
    }
    case 'SHOW_TABLE':
      return exactKeys(value, ['type', 'target', 'value']) && ['chat', 'dashboard', 'both'].includes(String(value.target)) && isRecord(value.value) && exactKeys(value.value, ['columns']) && Array.isArray(value.value.columns) && value.value.columns.every(item => typeof item === 'string' && targetPattern.test(item))
    case 'RESET_FILTER':
      return exactKeys(value, ['type', 'target']) && (value.target === undefined || validTarget)
    default:
      return false
  }
}

export function validateChatResponse(value: unknown): ChatResponse {
  if (!isRecord(value) || !['ok', 'fallback', 'error'].includes(String(value.status))) throw new Error('Invalid chat status')
  if (!exactKeys(value, ['status', 'question', 'answer', 'data', 'chart_spec', 'ui_actions', 'metadata'])) throw new Error('Unexpected chat response field')
  if (typeof value.question !== 'string' || !isRecord(value.answer) || !isRecord(value.data) || !isRecord(value.metadata)) throw new Error('Invalid chat response shape')
  if (!Array.isArray(value.ui_actions) || !value.ui_actions.every(isAction)) throw new Error('Invalid UI action payload')
  const answer = value.answer
  if (!exactKeys(answer, ['summary', 'drivers', 'recommended_actions', 'caveats'])) throw new Error('Unexpected answer field')
  if (typeof answer.summary !== 'string' || !Array.isArray(answer.drivers) || !Array.isArray(answer.recommended_actions) || !Array.isArray(answer.caveats)) throw new Error('Invalid answer payload')
  if (!Array.isArray(value.data.columns) || !Array.isArray(value.data.rows)) throw new Error('Invalid data payload')
  if (!exactKeys(value.data, ['columns', 'rows', 'unit_format'])) throw new Error('Unexpected data field')
  if ('unit_format' in value.data && value.data.unit_format !== null && typeof value.data.unit_format !== 'string') throw new Error('Invalid unit_format payload')
  const metadata = value.metadata
  if (!exactKeys(metadata, ['trace_id', 'session_id', 'intent', 'resolved_context', 'execution_time_ms'])) throw new Error('Unexpected metadata field')
  if (typeof metadata.trace_id !== 'string' || typeof metadata.session_id !== 'string' || typeof metadata.intent !== 'string' || !isRecord(metadata.resolved_context) || typeof metadata.execution_time_ms !== 'number') throw new Error('Invalid metadata payload')
  if (value.chart_spec !== null && !isRecord(value.chart_spec)) throw new Error('Invalid chart payload')
  return value as ChatResponse
}
