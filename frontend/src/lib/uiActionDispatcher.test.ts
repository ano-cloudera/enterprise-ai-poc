import { describe, expect, it } from 'vitest'
import { applyUiAction, applyUiActions, initialDashboardState, removeAppliedContext } from './uiActionDispatcher'

describe('UI action dispatcher', () => {
  it('SET_FILTER updates only the requested filter', () => {
    const state = { ...initialDashboardState, filters: { region: ['Jawa Timur'], channel: ['General Trade'] } }
    const next = applyUiAction(state, { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] })
    expect(next.filters.region).toEqual(['Jawa Barat'])
    expect(next.filters.channel).toEqual(['General Trade'])
  })

  it('SET_DATE_RANGE changes date state', () => {
    const next = applyUiAction(initialDashboardState, { type: 'SET_DATE_RANGE', value: 'previous_month' })
    expect(next.date_range.preset).toBe('previous_month')
  })

  it('CHANGE_METRIC and CHANGE_DIMENSION update analytical state', () => {
    const next = applyUiActions(initialDashboardState, [
      { type: 'CHANGE_METRIC', value: 'sales_volume' },
      { type: 'CHANGE_DIMENSION', value: 'channel' },
    ])
    expect(next.metric).toBe('sales_volume')
    expect(next.dimension).toBe('channel')
  })

  it('HIGHLIGHT_CARD updates visible highlight state', () => {
    const next = applyUiAction(initialDashboardState, { type: 'HIGHLIGHT_CARD', target: 'region', value: 'Jawa Barat' })
    expect(next.highlights).toContainEqual({ target: 'region', value: 'Jawa Barat' })
  })

  it('RESET_FILTER resets one filter and reset-all predictably', () => {
    const filtered = applyUiActions(initialDashboardState, [
      { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] },
      { type: 'SET_FILTER', target: 'channel', value: ['Modern Trade'] },
    ])
    const one = applyUiAction(filtered, { type: 'RESET_FILTER', target: 'channel' })
    expect(one.filters.region).toEqual(['Jawa Barat'])
    expect(one.filters.channel).toEqual([])
    expect(applyUiAction(one, { type: 'RESET_FILTER' }).filters.region).toEqual([])
  })

  it('applies multiple actions in order', () => {
    const next = applyUiActions(initialDashboardState, [
      { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] },
      { type: 'SET_FILTER', target: 'region', value: ['Jawa Timur'] },
    ])
    expect(next.filters.region).toEqual(['Jawa Timur'])
    expect(next.revision).toBe(2)
  })

  it('ignores malformed and unknown actions without crashing', () => {
    expect(() => applyUiActions(initialDashboardState, [{ type: 'UNKNOWN' } as never, null as never])).not.toThrow()
    expect(applyUiActions(initialDashboardState, [{ type: 'UNKNOWN' } as never])).toEqual(initialDashboardState)
    expect(() => applyUiAction(initialDashboardState, { type: 'SET_DATE_RANGE', value: null } as never)).not.toThrow()
    expect(applyUiAction(initialDashboardState, { type: 'SET_DATE_RANGE', value: null } as never)).toBe(initialDashboardState)
  })

  it('tracks and removes AI-applied context', () => {
    const applied = applyUiAction(initialDashboardState, { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] })
    expect(applied.ai_applied_context).toContainEqual(expect.objectContaining({ target: 'region', label: 'Jawa Barat' }))
    const removed = removeAppliedContext(applied, 'filter', 'region')
    expect(removed.filters.region).toEqual([])
    expect(removed.ai_applied_context).toEqual([])
  })

  it('RENDER_CHART and SHOW_TABLE create renderable chat state', () => {
    const next = applyUiActions(initialDashboardState, [
      { type: 'RENDER_CHART', target: 'chat', value: { chart_type: 'bar', dimension: 'product', metric: 'net_sales' } },
      { type: 'SHOW_TABLE', target: 'chat', value: { columns: ['dimension', 'value'] } },
    ])
    expect(next.chat.chart).toEqual(expect.objectContaining({ chart_type: 'bar' }))
    expect(next.chat.table).toEqual({ visible: true, columns: ['dimension', 'value'] })
  })
})
