import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DashboardStateProvider } from '../lib/dashboardState'
import { DashboardPage } from './DashboardPage'
import { api } from '../lib/api'

const overview = {
  period: 'Current Month',
  kpis: [{ key: 'net_sales', label: 'Net Sales', value: 276400, format: 'currency_billion', delta: 5.8 }],
  sales_trend: [{ month: '2024-02', sales: 260000 }, { month: '2024-03', sales: 276400 }],
  region_sales: [{ region: 'Jawa Barat', sales: 75521 }],
  top_products: [{ product: 'Bodrex', category: 'Analgesic', sales: 60000 }],
  channel_share: [{ channel: 'Modern Trade', sales: 126400, share: 100 }],
  ai_insight: { headline: 'Review context', summary: 'Governed summary', actions: [] },
}
let fetchResult = { data: overview, loading: false, error: null as string | null }

vi.mock('../hooks/useFetch', () => ({ useFetch: () => fetchResult }))
vi.mock('../lib/api', () => ({ api: { chat: vi.fn(), dashboard: vi.fn() } }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))

describe('floating AI shared dashboard state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchResult = { data: overview, loading: false, error: null }
  })
  afterEach(cleanup)

  it('synchronizes auto-applied filters, shows chips, and restores the previous state', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Bagaimana sales Bodrex di Jawa Barat?',
      answer: { summary: 'Sales result.', drivers: [], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null,
      ui_actions: [
        { type: 'SET_FILTER', target: 'product', value: ['Bodrex'] },
        { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] },
        { type: 'SET_DATE_RANGE', value: 'current_month' },
      ],
      metadata: { trace_id: 't', session_id: 's', intent: 'analysis', resolved_context: {} as never, execution_time_ms: 1 },
    } as never)
    render(<DashboardStateProvider><DashboardPage /></DashboardStateProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.change(screen.getByPlaceholderText('Ask about this dashboard...'), { target: { value: 'Bagaimana sales Bodrex di Jawa Barat?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await waitFor(() => expect((screen.getByLabelText('Region') as HTMLSelectElement).value).toBe('Jawa Barat'))
    expect((screen.getByLabelText('Product') as HTMLSelectElement).value).toBe('Bodrex')
    screen.getByText('Applied by AI:')
    screen.getByRole('button', { name: 'Remove Jawa Barat' })
    screen.getByRole('button', { name: 'Remove Bodrex' })
    screen.getByRole('button', { name: 'Remove Mar 2024' })

    fireEvent.click(within(screen.getByRole('dialog', { name: 'SCAN' })).getByRole('button', { name: 'Undo AI changes' }))
    expect((screen.getByLabelText('Region') as HTMLSelectElement).value).toBe('')
    expect((screen.getByLabelText('Product') as HTMLSelectElement).value).toBe('')
    expect(screen.queryByText('Applied by AI:')).toBeNull()
  })

  it('keeps the open assistant and its answer mounted while dashboard data refreshes', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Kenapa sales turun bulan ini?',
      answer: { summary: 'Sales turun dibanding periode sebelumnya.', drivers: [], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null, ui_actions: [],
      metadata: { trace_id: 't', session_id: 's', intent: 'analysis', resolved_context: {} as never, execution_time_ms: 1 },
    } as never)
    const view = render(<DashboardStateProvider><DashboardPage /></DashboardStateProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.click(screen.getByRole('button', { name: 'Kenapa sales turun bulan ini?' }))
    await screen.findByText('Sales turun dibanding periode sebelumnya.')

    fetchResult = { data: overview, loading: true, error: null }
    view.rerender(<DashboardStateProvider><DashboardPage /></DashboardStateProvider>)

    screen.getByRole('dialog', { name: 'SCAN' })
    screen.getByText('Sales turun dibanding periode sebelumnya.')
  })

  it('shows a controlled empty state for market signals in the default All Products context', () => {
    render(<DashboardStateProvider><DashboardPage /></DashboardStateProvider>)
    expect(document.getElementById('key-business-signals')).toBeNull()
    screen.getByText('Select a product or category to view external market signals.')
    screen.getByText('Use the Product filter or Ask AI to explore market intelligence.')
  })

  it('shows governed market signals once a product context is applied', async () => {
    fetchResult = { data: { ...overview, market_signals: { opportunity_score: 47.9, competitive_pressure: 55.5, weather_correlation: -0.3 } }, loading: false, error: null }
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Bagaimana Bodrex?',
      answer: { summary: 'Sales result.', drivers: [], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null,
      ui_actions: [{ type: 'SET_FILTER', target: 'product', value: ['Bodrex'] }],
      metadata: { trace_id: 't', session_id: 's', intent: 'analysis', resolved_context: {} as never, execution_time_ms: 1 },
    } as never)
    render(<DashboardStateProvider><DashboardPage /></DashboardStateProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.change(screen.getByPlaceholderText('Ask about this dashboard...'), { target: { value: 'Bagaimana Bodrex?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await waitFor(() => expect((screen.getByLabelText('Product') as HTMLSelectElement).value).toBe('Bodrex'))
    expect(screen.queryByText('Select a product or category to view external market signals.')).toBeNull()
    expect(screen.getAllByText('47.9').length).toBeGreaterThan(0)
    expect(screen.getAllByText('55.5').length).toBeGreaterThan(0)
    expect(screen.getAllByText('-0.30').length).toBeGreaterThan(0)
  })

})
