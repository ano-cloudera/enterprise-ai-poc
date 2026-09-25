import { describe, expect, it } from 'vitest'

import { validateChatResponse } from './contract'

function baseResponse(overrides: Record<string, unknown> = {}) {
  return {
    status: 'ok',
    question: 'Berapa Gross Sales Q4?',
    answer: { summary: 'Gross Sales naik.', drivers: [], recommended_actions: [], caveats: [] },
    data: { columns: ['calmonth', 'metric_value'], rows: [{ calmonth: 202410, metric_value: 100 }] },
    chart_spec: null,
    ui_actions: [],
    metadata: {
      trace_id: 't1',
      session_id: 's1',
      intent: 'ossie_analytical',
      resolved_context: { filters: {}, date_range: { preset: null, start: null, end: null }, metric: 'x', dimension: 'y', highlights: [], ai_applied_context: [], revision: 1, chat: { chart: null, table: { visible: false, columns: [] } } },
      execution_time_ms: 12,
    },
    ...overrides,
  }
}

describe('validateChatResponse', () => {
  it('accepts a response without unit_format (backward compatible)', () => {
    expect(() => validateChatResponse(baseResponse())).not.toThrow()
  })

  it('accepts a response with data.unit_format set to a string', () => {
    // Regression: backend now sends QueryData.unit_format (see
    // TempoOssieRegistry.metric_definition -> chat.py), and this validator's
    // exactKeys() check previously rejected it as an "Unexpected data field",
    // throwing on every real analytical answer and surfacing as the generic
    // "Unable to complete the analysis right now" error in the UI - even
    // though the backend response was entirely valid.
    const response = baseResponse({ data: { columns: ['metric_value'], rows: [{ metric_value: 18188080 }], unit_format: 'quantity' } })
    expect(() => validateChatResponse(response)).not.toThrow()
  })

  it('accepts a response with data.unit_format set to null', () => {
    const response = baseResponse({ data: { columns: [], rows: [], unit_format: null } })
    expect(() => validateChatResponse(response)).not.toThrow()
  })

  it('rejects a non-string, non-null unit_format', () => {
    const response = baseResponse({ data: { columns: [], rows: [], unit_format: 42 } })
    expect(() => validateChatResponse(response)).toThrow()
  })

  it('still rejects a genuinely unexpected data field', () => {
    const response = baseResponse({ data: { columns: [], rows: [], made_up_field: 'x' } })
    expect(() => validateChatResponse(response)).toThrow()
  })
})
