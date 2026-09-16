import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MonitoringPage } from './MonitoringPage'

vi.mock('../hooks/useFetch', () => ({
  useFetch: () => ({
    data: {
      total_queries: 12,
      avg_response_time_ms: 850,
      success_rate: 99.2,
      validation_reject_rate: 0.8,
      usage_trend: [],
      recent_activity: [],
    },
    loading: false,
    error: null,
  }),
}))

describe('AI Monitoring page introduction', () => {
  afterEach(cleanup)

  it('identifies the page as an operational AI workspace', () => {
    render(<MonitoringPage />)

    expect(screen.queryByText(/AI Operations/i)).toBeNull()
    expect(screen.getByRole('heading', { name: 'AI Monitoring' })).toBeTruthy()
  })
})
