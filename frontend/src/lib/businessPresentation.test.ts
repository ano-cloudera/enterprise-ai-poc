import { describe, expect, it } from 'vitest'

import { formatBusinessValue, formatCalmonthDisplay, parseCalmonth } from './businessPresentation'

describe('calmonth display', () => {
  it('formats YYYYMM integers as month labels', () => {
    expect(formatCalmonthDisplay(202411)).toBe('Nov 2024')
    expect(formatCalmonthDisplay(202410)).toBe('Okt 2024')
  })

  it('parses comma-separated numeric strings from tables', () => {
    expect(parseCalmonth('202,411')).toBe(202411)
    expect(formatBusinessValue('calmonth', 202411)).toBe('Nov 2024')
  })

  it('does not locale-format calmonth as a generic number', () => {
    expect(formatBusinessValue('calmonth', 202410)).not.toContain(',')
    expect(formatBusinessValue('calmonth', 202410)).toBe('Okt 2024')
  })
})
