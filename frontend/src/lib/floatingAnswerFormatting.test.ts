import { describe, expect, it } from 'vitest'

import { formatFloatingAnswerText, formatFloatingDriver } from './floatingAnswerFormatting'

describe('floating answer business formatting', () => {
  it('formats long sales and percentage values for business users', () => {
    expect(formatFloatingAnswerText(
      'Nilai Jawa Barat berubah 18.21664440535221% dibanding periode sebelumnya, dari 32568.457000000002 menjadi 38501.337000000004.'
    )).toBe('Nilai Jawa Barat berubah +18.2% dibanding periode sebelumnya, dari Rp32.57B menjadi Rp38.50B.')
  })

  it('removes raw technical evidence from drivers', () => {
    expect(formatFloatingDriver(
      'Trusted comparison: Jawa Barat is the leading returned comparison row. Evidence: current_value=38501.337000000004; previous_value=32568.457000000002; percentage_change=18.21664440535221'
    )).toBe('Trusted comparison: Jawa Barat is the leading returned comparison row.')
  })

  it('turns a raw comparison payload into readable business labels', () => {
    expect(formatFloatingAnswerText(
      'current_value=38501.337000000004; previous_value=32568.457000000002; absolute_change=5932.880000000001; percentage_change=18.21664440535221'
    )).toBe('Current sales: Rp38.50B • Previous period: Rp32.57B • Change: +Rp5.93B • Change percentage: +18.2%')
  })

  it('hides technical-only provenance drivers', () => {
    expect(formatFloatingDriver('Provenance: source_type=synthetic; data_confidence=calibrated')).toBe('')
  })
})
