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

  it('honors an explicit unit_format over the field/metric-name heuristics', () => {
    // Regression for the bug where every governed metric's SQL result column
    // is generically named "metric_value" - the word "value" in that name
    // matched the currency heuristic even for quantity/percent metrics
    // (e.g. sat_idm_store_stock_quantity, sat_oos_rate), formatting a stock
    // count or an out-of-stock rate as if it were IDR currency.
    expect(formatBusinessValue('metric_value', 18188080, undefined, 'quantity')).toBe('18,188,080')
    expect(formatBusinessValue('metric_value', 7.54, undefined, 'percent')).toBe('+7.5%')
    expect(formatBusinessValue('metric_value', 359901959512.19, undefined, 'currency_idr')).toBe('Rp359901.96T')
    expect(formatBusinessValue('metric_value', 0.42, undefined, 'ratio')).toBe('0.42')
    expect(formatBusinessValue('metric_value', 12.5, undefined, 'minutes')).toBe('12.5 min')
    // No unit_format supplied - falls back to the old heuristics unchanged,
    // so non-governed domains (forecast/weather) keep working as before.
    expect(formatBusinessValue('metric_value', 38501.337, undefined, undefined)).toBe('Rp38.50B')
  })

  it('converts internal field names to readable labels', () => {
    expect(formatBusinessLabel('net_sales')).toBe('Net Sales')
    expect(formatBusinessLabel('percentage_change')).toBe('Percentage Change')
  })

  it('builds compact context without null or internal enum values', () => {
    expect(businessContextItems({
      filters: { region: ['Jawa Barat'], product: [], channel: [] },
      date_range: { preset: 'current_month', start: null, end: null },
      metric: 'net_sales',
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
