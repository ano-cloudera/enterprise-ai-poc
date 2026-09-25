import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DashboardStateProvider } from '../lib/dashboardState'
import { AskAIPage } from './AskAIPage'
import { DashboardPage } from './DashboardPage'
import { api } from '../lib/api'

// The dashboard no longer hosts its own chat surface (see DashboardPage.test.tsx:
// "does not render a floating AI chat entry point"). All conversational AI now
// goes through the Ask AI page, but it still needs to update the SAME shared
// dashboard state the dashboard reads from -- that's the whole point of
// applyDashboardAiActions over the plain applyActions used for manual filters.
// These tests render Ask AI and Dashboard side by side under one real
// DashboardStateProvider (no dashboardState mock) to prove that contract still
// holds end to end now that the floating drawer is gone.

const overview = {
  period: 'Current Month',
  kpis: [{ key: 'net_sales', label: 'Net Sales', value: 276400, format: 'currency_billion', delta: 5.8 }],
  sales_trend: [{ month: '2024-02', sales: 260000 }, { month: '2024-03', sales: 276400 }],
  region_sales: [{ region: 'Jawa Barat', sales: 75521 }],
  top_products: [{ product: 'Bodrex', category: 'Analgesic', sales: 60000 }],
  channel_share: [{ channel: 'Modern Trade', sales: 126400, share: 100 }],
  ai_insight: { headline: 'Review context', summary: 'Governed summary', actions: [] },
}
let fetchResult: { data: any; loading: boolean; error: string | null } = {
  data: overview,
  loading: false,
  error: null,
}
const projectConfig = {
  project_name: 'Tempo Scan Commercial Intelligence Assistant',
  semantic_capabilities_enabled: false,
}

vi.mock('../hooks/useFetch', () => ({ useFetch: () => fetchResult }))
vi.mock('../lib/api', () => ({ api: { chat: vi.fn(), dashboard: vi.fn(), semanticCapabilities: vi.fn() } }))
vi.mock('../lib/project', () => ({ useProject: () => ({ config: projectConfig }) }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }))

describe('AI actions applied from Ask AI reach the shared dashboard state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    projectConfig.semantic_capabilities_enabled = false
    fetchResult = { data: overview, loading: false, error: null }
    // jsdom doesn't implement scrollIntoView; AskAIPage calls it to keep the
    // conversation scrolled to the latest message.
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
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
    render(<DashboardStateProvider><AskAIPage /><DashboardPage /></DashboardStateProvider>)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Bagaimana sales Bodrex di Jawa Barat?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await waitFor(() => expect((screen.getByLabelText('Region') as HTMLSelectElement).value).toBe('Jawa Barat'))
    expect((screen.getByLabelText('Product') as HTMLSelectElement).value).toBe('Bodrex')
    screen.getByText('Applied by AI:')
    screen.getByRole('button', { name: 'Remove Jawa Barat' })
    screen.getByRole('button', { name: 'Remove Bodrex' })
    screen.getByRole('button', { name: 'Remove Mar 2024' })

    fireEvent.click(screen.getByRole('button', { name: 'Undo AI changes' }))
    expect((screen.getByLabelText('Region') as HTMLSelectElement).value).toBe('')
    expect((screen.getByLabelText('Product') as HTMLSelectElement).value).toBe('')
    expect(screen.queryByText('Applied by AI:')).toBeNull()
  })

  it('shows a controlled empty state for market signals in the default All Products context', () => {
    render(<DashboardStateProvider><DashboardPage /></DashboardStateProvider>)
    expect(document.getElementById('key-business-signals')).toBeNull()
    screen.getByText('Select a product or category to view external market signals.')
    screen.getByText('Use the Product filter or Ask AI to explore market intelligence.')
  })

  it('shows governed market signals once a product context is applied from Ask AI', async () => {
    fetchResult = { data: { ...overview, market_signals: { opportunity_score: 47.9, competitive_pressure: 55.5, weather_correlation: -0.3 } }, loading: false, error: null }
    vi.mocked(api.chat).mockResolvedValue({
      status: 'ok', question: 'Bagaimana Bodrex?',
      answer: { summary: 'Sales result.', drivers: [], recommended_actions: [], caveats: [] },
      data: { columns: [], rows: [] }, chart_spec: null,
      ui_actions: [{ type: 'SET_FILTER', target: 'product', value: ['Bodrex'] }],
      metadata: { trace_id: 't', session_id: 's', intent: 'analysis', resolved_context: {} as never, execution_time_ms: 1 },
    } as never)
    render(<DashboardStateProvider><AskAIPage /><DashboardPage /></DashboardStateProvider>)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Bagaimana Bodrex?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await waitFor(() => expect((screen.getByLabelText('Product') as HTMLSelectElement).value).toBe('Bodrex'))
    expect(screen.queryByText('Select a product or category to view external market signals.')).toBeNull()
    expect(screen.getAllByText('47.9').length).toBeGreaterThan(0)
    expect(screen.getAllByText('55.5').length).toBeGreaterThan(0)
    expect(screen.getAllByText('-0.30').length).toBeGreaterThan(0)
  })

  it('renders the opt-in Impala/Ossie dashboard without synthetic forecast or market claims', () => {
    projectConfig.semantic_capabilities_enabled = true
    fetchResult = {
      data: {
        profile: 'impala_ossie',
        period: 'Q4 2024',
        kpis: [
          { key: 'gross_billing_value', label: 'Gross Sales', value: 127465426308, format: 'currency_idr', delta: 6.6 },
          { key: 'growth', label: 'Growth', value: 6.6, format: 'percent', delta: 6.6 },
          { key: 'fill_rate', label: 'Fill Rate', value: 79.52, format: 'percent', delta: null },
          { key: 'top_material', label: 'Top Material', value: '035-28-07', format: 'text', delta: null },
        ],
        sales_trend: [{ month: '202410', sales: 137196.03 }, { month: '202411', sales: 119525.12 }, { month: '202412', sales: 127465.43 }],
        region_sales: [{ region: '0201', sales: 8000 }],
        top_products: [{ product: '035-28-07', category: 'Material', sales: 5000 }],
        channel_share: [{ channel: 'Sell-In', sales: 384186.58, share: 91.4 }, { channel: 'Sell-Out', sales: 35990.2, share: 8.6 }],
        labels: {
          sales_trend: 'Gross Sales Trend',
          region_sales: 'Sell-In by Sales Office',
          top_products: 'Top Materials',
          channel_share: 'Sell-In vs Sell-Out Context',
        },
        scope_badges: ['Q4 2024', 'Gross Sales = BILL_VAL'],
        ai_insight: { headline: 'Governed', summary: 'Audited Impala Gold semantic views.', actions: [] },
      },
      loading: false,
      error: null,
    }

    render(<DashboardStateProvider><DashboardPage /></DashboardStateProvider>)

    screen.getByText('Gross Sales (BILL_VAL)')
    screen.getByText('Company Fill Rate')
    screen.getByText('Top Material')
    screen.getByText('Sell-In by Sales Office')
    screen.getByText('Top Materials')
    screen.getByText('Sell-In vs Sell-Out Context')
    screen.getByText('Audited Impala Gold semantic views.')
    expect(screen.queryByText('Forecast Next Period')).toBeNull()
    expect(screen.queryByText('Market Opportunity')).toBeNull()
    expect(screen.queryByLabelText('Region')).toBeNull()
  })
})
