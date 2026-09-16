import { describe, expect, it } from 'vitest'

import { businessContextItems, formatBusinessLabel, formatBusinessValue, suggestedFollowUps } from './businessPresentation'

describe('business presentation', () => {
  it('formats governed measures without changing their raw values', () => {
    expect(formatBusinessValue('net_sales', 38501.337000000004)).toBe('Rp38.50B')
    expect(formatBusinessValue('percentage_change', 18.21664440535221)).toBe('+18.2%')
    expect(formatBusinessValue('correlation', 0.297123)).toBe('0.30')
    expect(formatBusinessValue('row_count', 1200.9)).toBe('1,201')
    expect(formatBusinessValue('opportunity_score', 66.3588)).toBe('66.4')
  })

  it('converts internal field names to readable labels', () => {
    expect(formatBusinessLabel('net_sales')).toBe('Net Sales')
    expect(formatBusinessLabel('percentage_change')).toBe('Percentage Change')
  })

  it('builds compact context without null or internal enum values', () => {
    expect(businessContextItems({
      filters: { region: ['Jawa Barat'], product: [], channel: [] },
      date_range: { preset: 'current_month', start: null, end: null },
      metric: 'net_sales', dimension: 'region', highlights: [], ai_applied_context: [], revision: 0,
      chat: { chart: null, table: { visible: false, columns: [] } },
    })).toEqual([
      { label: 'Period', value: 'Current Month' },
      { label: 'Region', value: 'Jawa Barat' },
      { label: 'Product', value: 'All Products' },
      { label: 'Channel', value: 'All Channels' },
      { label: 'Metric', value: 'Net Sales' },
    ])
  })

  it('returns contextual business follow-ups with a maximum of four', () => {
    expect(suggestedFollowUps('market')).toEqual([
      'Which region has the highest opportunity?',
      'Compare Bodrex with key competitors',
      'Where is the largest distribution gap?',
    ])
    expect(suggestedFollowUps('forecast')).toHaveLength(3)
  })
})
