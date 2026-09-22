import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DashboardPage } from './DashboardPage'

const dashboardState = {
  filters: { region: [], product: [], category: [], channel: [], outlet: [], customer_segment: [] },
  date_range: { preset: 'current_month', start: null, end: null },
  metric: 'net_sales', dimension: 'region', highlights: [], ai_applied_context: [], revision: 0,
  chat: { chart: null, table: { visible: false, columns: [] } },
}
const stateActions = { applyActions: vi.fn(), undoAiChanges: vi.fn(), setFilter: vi.fn(), removeAppliedContext: vi.fn(), reset: vi.fn(), previousDashboardState: null }
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

describe('Dashboard v2', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => { cleanup() })

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

  it('applies date range changes through the shared dashboard action dispatcher', () => {
    render(<DashboardPage />)
    fireEvent.change(screen.getByLabelText('Date Range'), { target: { value: 'previous_month' } })
    expect(stateActions.applyActions).toHaveBeenCalledWith([{ type: 'SET_DATE_RANGE', value: 'previous_month' }])
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

  // The dashboard no longer hosts its own chat surface (floating "Ask AI"
  // drawer): all conversational AI, including changes it applies to this
  // shared dashboard state, now goes exclusively through the Ask AI page.
  // Duplicating a second chat UI here caused divergent behavior/copy from
  // Ask AI's StructuredAnswer and a confusing "two chatbots" experience.
  it('does not render a floating AI chat entry point on the dashboard', () => {
    render(<DashboardPage />)
    expect(screen.queryByRole('button', { name: 'Ask AI' })).toBeNull()
    expect(screen.queryByRole('dialog', { name: 'SCAN' })).toBeNull()
  })

  it('uses functional enterprise icons for filters', () => {
    const { container } = render(<DashboardPage />)
    expect(container.querySelector('.lucide-calendar-days')).toBeTruthy()
    expect(container.querySelector('.lucide-map-pin')).toBeTruthy()
    expect(container.querySelector('.lucide-package')).toBeTruthy()
    expect(container.querySelector('.lucide-store')).toBeTruthy()
  })
})
