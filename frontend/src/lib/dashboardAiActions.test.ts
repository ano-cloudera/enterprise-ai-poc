import { describe, expect, it } from 'vitest'

import { actionLabel, dashboardSectionForAction, dashboardSectionForTopic, partitionDashboardAiActions, selectDashboardActions } from './dashboardAiActions'

describe('floating dashboard AI action policy', () => {
  it('auto-applies only supported simple filters and date ranges', () => {
    const result = partitionDashboardAiActions([
      { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] },
      { type: 'SET_FILTER', target: 'product', value: ['Bodrex'] },
      { type: 'SET_FILTER', target: 'channel', value: ['Modern Trade'] },
      { type: 'SET_DATE_RANGE', value: 'current_month' },
    ])

    expect(result.automatic).toHaveLength(4)
    expect(result.confirmationRequired).toEqual([])
    expect(result.rejected).toEqual([])
  })

  it('requires confirmation for larger visual actions', () => {
    const result = partitionDashboardAiActions([
      { type: 'CHANGE_DIMENSION', value: 'channel' },
      { type: 'CHANGE_METRIC', value: 'units' },
      { type: 'RENDER_CHART', target: 'dashboard', value: { chart_type: 'bar', dimension: 'channel', metric: 'net_sales' } },
      { type: 'SHOW_TABLE', target: 'dashboard', value: { columns: ['channel', 'sales'] } },
      { type: 'HIGHLIGHT_CARD', target: 'growth', value: 'growth' },
    ])

    expect(result.automatic).toEqual([])
    expect(result.confirmationRequired).toHaveLength(5)
  })

  it('rejects unsupported filters and malformed or unknown commands', () => {
    const invalid = [
      { type: 'SET_FILTER', target: 'inventory', value: ['low'] },
      { type: 'SET_FILTER', target: 'region', value: 'Jawa Barat' },
      { type: 'SET_DATE_RANGE', value: { start: '2024-03-01' } },
      { type: 'EXECUTE_JAVASCRIPT', value: 'alert(1)' },
    ]
    const result = partitionDashboardAiActions(invalid)

    expect(result.automatic).toEqual([])
    expect(result.confirmationRequired).toEqual([])
    expect(result.rejected).toEqual(invalid)
  })

  it('maps validated actions to dashboard sections deterministically', () => {
    expect(dashboardSectionForTopic('trend')).toBe('sales-performance')
    expect(dashboardSectionForTopic('region')).toBe('sales-by-region')
    expect(dashboardSectionForTopic('product')).toBe('product-performance')
    expect(dashboardSectionForTopic('channel')).toBe('channel-contribution')
    expect(dashboardSectionForTopic('market')).toBe('market-signals')
    expect(dashboardSectionForAction({ type: 'CHANGE_DIMENSION', value: 'region' })).toBe('sales-by-region')
    expect(dashboardSectionForAction({ type: 'CHANGE_DIMENSION', value: 'product' })).toBe('product-performance')
    expect(dashboardSectionForAction({ type: 'CHANGE_DIMENSION', value: 'channel' })).toBe('channel-contribution')
    expect(dashboardSectionForAction({ type: 'SHOW_TABLE', target: 'dashboard', value: { columns: ['product'] } })).toBe('product-performance')
    expect(dashboardSectionForAction({ type: 'HIGHLIGHT_CARD', target: 'market', value: 'opportunity' })).toBe('market-signals')
    expect(dashboardSectionForAction({ type: 'CHANGE_METRIC', value: 'net_sales' })).toBe('sales-performance')
  })

  it('uses business-facing labels without leaking action mechanics', () => {
    expect(actionLabel({ type: 'CHANGE_DIMENSION', value: 'region' })).toBe('Compare regions')
    expect(actionLabel({ type: 'CHANGE_DIMENSION', value: 'product' })).toBe('View product drivers')
    expect(actionLabel({ type: 'CHANGE_DIMENSION', value: 'channel' })).toBe('Compare channels')
    expect(actionLabel({ type: 'CHANGE_METRIC', value: 'net_sales' })).toBe('View Net Sales')
    expect(actionLabel({ type: 'SHOW_TABLE', target: 'dashboard', value: { columns: ['product'] } })).toBe('View supporting data')
    expect(actionLabel({ type: 'RENDER_CHART', target: 'dashboard', value: { chart_type: 'bar', dimension: 'region', metric: 'net_sales' } })).toBe('Compare regions')
  })

  it('selects at most two relevant dashboard actions', () => {
    const actions = selectDashboardActions([
      { type: 'CHANGE_DIMENSION', value: 'region' },
      { type: 'CHANGE_DIMENSION', value: 'product' },
      { type: 'CHANGE_DIMENSION', value: 'channel' },
    ])
    expect(actions).toHaveLength(2)
    expect(actions.map(actionLabel)).toEqual(['Compare regions', 'View product drivers'])
  })

  it('prioritizes contextual dashboard actions over a generic metric action', () => {
    const actions = selectDashboardActions([
      { type: 'CHANGE_METRIC', value: 'net_sales' },
      { type: 'CHANGE_DIMENSION', value: 'channel' },
      { type: 'RENDER_CHART', target: 'chat', value: { chart_type: 'bar', dimension: 'channel', metric: 'net_sales' } },
    ])

    expect(actions.map(actionLabel)).toEqual(['Compare channels', 'View Net Sales'])
  })
})
