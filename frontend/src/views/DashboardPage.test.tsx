import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DashboardPage } from './DashboardPage'
import { api } from '../lib/api'

const dashboardState = {
  filters: { region: [], product: [], category: [], channel: [], outlet: [], customer_segment: [] },
  date_range: { preset: 'current_month', start: null, end: null },
  metric: 'net_sales', dimension: 'region', highlights: [], ai_applied_context: [], revision: 0,
  chat: { chart: null, table: { visible: false, columns: [] } },
}
const stateActions = { applyActions: vi.fn(), applyDashboardAiActions: vi.fn(), undoAiChanges: vi.fn(), setFilter: vi.fn(), removeAppliedContext: vi.fn(), reset: vi.fn(), previousDashboardState: null, aiAppliedActions: [] }
const push = vi.fn()
const overview = {
  period: 'Current Month',
  kpis: [
    { key: 'net_sales', label: 'Net Sales', value: 276400, format: 'currency_billion', delta: 5.8 },
    { key: 'growth', label: 'Growth vs Comparison', value: 5.8, format: 'percent', delta: 5.8 },
    { key: 'inventory', label: 'Inventory Health', value: 95, format: 'percent', delta: null },
    { key: 'top_region', label: 'Top Region', value: 'Jawa Barat', format: 'text', delta: null },
  ],
  sales_trend: [{ month: '2024-01', sales: 250000 }, { month: '2024-02', sales: 260000 }, { month: '2024-03', sales: 276400 }],
  region_sales: [{ region: 'Jawa Barat', sales: 75521 }, { region: 'Jawa Timur', sales: 62000 }],
  top_products: [{ product: 'Tempra', category: 'Fever & Pain', sales: 60000 }],
  channel_share: [{ channel: 'General Trade', sales: 150000, share: 54.3 }, { channel: 'Modern Trade', sales: 126400, share: 45.7 }],
  market_signals: { market_growth: 6.2, competitive_pressure: 55.5, distribution_gap: 10.5, weather_correlation: -0.3 },
  ai_insight: { headline: 'Review context', summary: 'Governed summary', actions: [] },
}

vi.mock('../hooks/useFetch', () => ({ useFetch: () => ({ data: overview, loading: false, error: null }) }))
vi.mock('../lib/dashboardState', () => ({ useDashboardState: () => ({ state: dashboardState, ...stateActions }) }))
vi.mock('../lib/api', () => ({ api: { chat: vi.fn() } }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))

describe('Dashboard v2', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => { cleanup(); vi.useRealTimers() })

  it('renders executive header, compact filters, and five governed KPI slots', () => {
    render(<DashboardPage />)
    expect(screen.queryByText(/^Commercial Intelligence$/i)).toBeNull()
    screen.getByRole('heading', { name: 'Commercial Dashboard' })
    for (const label of ['Date Range', 'Region', 'Product', 'Channel']) screen.getByLabelText(label)
    for (const label of ['Net Sales', 'Growth vs Previous Period', 'Forecast Next Period', 'Top Region', 'Market Opportunity']) screen.getByText(label)
    expect(screen.queryByText('Inventory Health')).toBeNull()
    expect(screen.getAllByText('Not available').length).toBeGreaterThanOrEqual(2)
  })

  it('updates shared filter state and never renders raw missing values', () => {
    const { container } = render(<DashboardPage />)
    fireEvent.change(screen.getByLabelText('Region'), { target: { value: 'Jawa Barat' } })
    expect(stateActions.setFilter).toHaveBeenCalledWith('region', ['Jawa Barat'])
    expect(container.textContent).not.toMatch(/null|undefined|NaN|None → None/)
  })

  it('uses compact executive proportions for trend, signals, and analytical rows', () => {
    render(<DashboardPage />)
    const sales = document.getElementById('sales-performance')
    const region = document.getElementById('sales-by-region')
    const product = document.getElementById('product-performance')
    const channel = document.getElementById('channel-contribution')
    const market = document.getElementById('market-signals')

    expect(document.getElementById('key-business-signals')).toBeNull()
    expect(screen.queryByText('Key Business Signals')).toBeNull()
    expect([...sales!.querySelectorAll('div')].some(element => element.className.includes('sm:h-[300px]'))).toBe(true)
    expect(region?.className).toContain('xl:col-span-5')
    expect(product?.className).toContain('xl:col-span-7')
    expect(channel?.className).toContain('xl:col-span-5')
    expect(market?.className).toContain('xl:col-span-7')
    expect(screen.getAllByText('+6.2%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('55.5').length).toBeGreaterThan(0)
    expect(screen.getAllByText('10.5%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('-0.30').length).toBeGreaterThan(0)
  })


  it('opens and closes the floating AI drawer without navigating away', () => {
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    screen.getByRole('dialog', { name: 'SCAN' })
    screen.getByText('Kenapa sales turun bulan ini?')
    for (const item of ['Mar 2024', 'All Regions', 'All Products', 'All Channels']) expect(screen.getAllByText(item).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Close AI assistant' }))
    expect(screen.queryByRole('dialog', { name: 'SCAN' })).toBeNull()
  })

  it('auto-applies simple filters and dimension changes but waits for confirmation before a large chart/table action', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Tampilkan breakdown berdasarkan channel',
      answer: { summary: 'Sales decline is concentrated in General Trade.', drivers: ['General Trade is the largest negative contributor.'], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null,
      ui_actions: [
        { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] },
        { type: 'CHANGE_DIMENSION', value: 'region' },
        { type: 'CHANGE_METRIC', value: 'units' },
        { type: 'SHOW_TABLE', target: 'dashboard', value: { columns: ['channel', 'sales'] } },
      ],
      metadata: { trace_id: 't', session_id: 's', intent: 'analysis', resolved_context: dashboardState, execution_time_ms: 1 },
    } as never)
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.click(screen.getByRole('button', { name: 'Channel mana yang paling terdampak?' }))

    await waitFor(() => expect(stateActions.applyDashboardAiActions).toHaveBeenCalledWith([
      { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] },
      { type: 'CHANGE_DIMENSION', value: 'region' },
    ]))
    expect(stateActions.applyActions).not.toHaveBeenCalled()
    screen.getByText('Sales decline is concentrated in General Trade.')
    screen.getByText('General Trade is the largest negative contributor.')
    expect(push).not.toHaveBeenCalled()
    const metricAction = screen.getByRole('button', { name: 'View Units' })
    screen.getByRole('button', { name: 'View supporting data' })
    fireEvent.click(metricAction)
    expect(stateActions.applyActions).toHaveBeenCalledWith([{ type: 'CHANGE_METRIC', value: 'units' }])
    screen.getByRole('dialog', { name: 'SCAN' })
  })

  it('auto-applies a highlight action reported to the dashboard', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Produk dan channel mana yang terdampak?',
      answer: { summary: 'A governed result is available.', drivers: [], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null,
      ui_actions: [{ type: 'CHANGE_DIMENSION', value: 'product' }, { type: 'HIGHLIGHT_CARD', target: 'growth', value: 'growth' }],
      metadata: { trace_id: 't', session_id: 's', intent: 'analysis', resolved_context: dashboardState, execution_time_ms: 1 },
    } as never)
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.change(screen.getByPlaceholderText('Ask about this dashboard...'), { target: { value: 'Produk dan channel mana yang terdampak?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await waitFor(() => expect(stateActions.applyDashboardAiActions).toHaveBeenCalledWith([
      { type: 'CHANGE_DIMENSION', value: 'product' },
      { type: 'HIGHLIGHT_CARD', target: 'growth', value: 'growth' },
    ]))
    expect(push).not.toHaveBeenCalled()
    screen.getByRole('dialog', { name: 'SCAN' })
    screen.getByText('Applied to dashboard')
  })

  it('rejects unsupported UI commands while retaining the analytical answer', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Question', answer: { summary: 'Safe answer', drivers: [], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null,
      ui_actions: [{ type: 'SET_FILTER', target: 'inventory', value: ['low'] }],
      metadata: { trace_id: 't', session_id: 's', intent: 'analysis', resolved_context: dashboardState, execution_time_ms: 1 },
    } as never)
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.change(screen.getByPlaceholderText('Ask about this dashboard...'), { target: { value: 'Question' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await screen.findByText('Safe answer')
    expect(stateActions.applyDashboardAiActions).not.toHaveBeenCalled()
    expect(stateActions.applyActions).not.toHaveBeenCalled()
  })

  it('renders a submitted answer in the drawer and hands off the existing answer on explicit escalation', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Analisa strategi Bodrex',
      answer: {
        summary: 'Nilai Bodrex berubah 18.21664440535221% dari 32568.457000000002 menjadi 38501.337000000004.',
        drivers: ['Trusted comparison. Evidence: current_value=38501.337000000004'],
        recommended_actions: [], caveats: [],
      },
      data: { columns: [], rows: [] }, chart_spec: null, ui_actions: [],
      metadata: { trace_id: 't', session_id: 's', intent: 'analysis', resolved_context: dashboardState, execution_time_ms: 1 },
    } as never)
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.change(screen.getByPlaceholderText('Ask about this dashboard...'), { target: { value: 'Analisa strategi Bodrex' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await screen.findByText('Summary')
    screen.getByText('Nilai Bodrex berubah +18.2% dari Rp32.57B menjadi Rp38.50B.')
    expect(screen.getByRole('dialog', { name: 'SCAN' }).textContent).not.toContain('current_value=')
    expect(push).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Continue analysis in Ask AI' }))
    expect(push).toHaveBeenCalledWith('/ask-ai')
    const handoff = JSON.parse(window.sessionStorage.getItem('scan.ask-ai.handoff') || '{}')
    expect(handoff.question).toBe('Analisa strategi Bodrex')
    expect(handoff.response.answer.summary).toBe('Nilai Bodrex berubah 18.21664440535221% dari 32568.457000000002 menjadi 38501.337000000004.')
  })

  it('shows a controlled business error without backend details', async () => {
    vi.mocked(api.chat).mockRejectedValue(new Error('500 traceback: database password leaked'))
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.click(screen.getByRole('button', { name: 'Kenapa sales turun bulan ini?' }))

    await screen.findByText('Unable to complete the analysis right now. Please try again.')
    expect(screen.getByRole('dialog', { name: 'SCAN' }).textContent).not.toContain('traceback')
  })

  it('submits floating chat with Enter and preserves Shift+Enter multiline input', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Forecast Bodrex', answer: { summary: 'Available', drivers: [], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null, ui_actions: [],
      metadata: { trace_id: 't', session_id: 's', intent: 'forecast', resolved_context: dashboardState, execution_time_ms: 1 },
    } as never)
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    const input = screen.getByPlaceholderText('Ask about this dashboard...') as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: 'Bandingkan Bodrex' } })
    expect(fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })).toBe(true)
    expect(api.chat).not.toHaveBeenCalled()
    fireEvent.change(input, { target: { value: 'Bandingkan Bodrex\ndengan kompetitor' } })
    expect(fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })).toBe(false)
    await waitFor(() => expect(api.chat).toHaveBeenCalledWith('Bandingkan Bodrex\ndengan kompetitor', expect.any(String), dashboardState))
  })

  it('uses a full-width mobile drawer and bounded desktop width', () => {
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    expect(screen.getByRole('dialog', { name: 'SCAN' }).className).toContain('w-full')
    expect(screen.getByRole('dialog', { name: 'SCAN' }).className).toContain('sm:max-w-[410px]')
  })

  it('sends the same shared dashboard context through the existing chat API', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Bagaimana forecast bulan depan?',
      answer: { summary: 'Available', drivers: [], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null, ui_actions: [],
      metadata: { trace_id: 't', session_id: 's', intent: 'forecast', resolved_context: dashboardState, execution_time_ms: 1 },
    } as never)
    render(<DashboardPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }))
    fireEvent.click(screen.getByRole('button', { name: 'Bagaimana forecast bulan depan?' }))
    await waitFor(() => expect(api.chat).toHaveBeenCalledWith('Bagaimana forecast bulan depan?', expect.any(String), dashboardState))
  })

  it('uses functional enterprise icons for filters and the AI assistant', () => {
    const { container } = render(<DashboardPage />)
    expect(container.querySelector('.lucide-calendar-days')).toBeTruthy()
    expect(container.querySelector('.lucide-map-pin')).toBeTruthy()
    expect(container.querySelector('.lucide-package')).toBeTruthy()
    expect(container.querySelector('.lucide-store')).toBeTruthy()
    expect(container.querySelector('.lucide-message-square-text')).toBeTruthy()
    expect(container.querySelector('.lucide-sparkles')).toBeNull()
  })
})
