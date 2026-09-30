import React from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../lib/api'
import { AppShell } from '../layout/AppShell'
import { ModelSelectionProvider } from '../lib/modelSelection'
import { AskDataPage } from './AskDataPage'

vi.mock('../lib/api', () => ({ api: { models: vi.fn(), randomQueries: vi.fn(), chatStream: vi.fn() } }))
vi.mock('next/navigation', () => ({ usePathname: () => '/' }))

describe('V2 Ask Data page', () => {
  afterEach(() => { vi.useRealTimers(); cleanup() })

  it('loads a real random question into the composer and streams progress', async () => {
    vi.mocked(api.models).mockResolvedValue({ models: [{ provider: 'qwen', id: 'qwen-model', label: 'Qwen Private', available: true, reason: null }] })
    vi.mocked(api.randomQueries).mockResolvedValue({ questions: [{ id: 'sales-1', question: 'Berapa total Gross Billing Value?', domain: 'sales', domains: ['sales'], difficulty: 'simple', analysis_type: 'metric', expected_visualization: 'kpi' }] })
    vi.mocked(api.chatStream).mockImplementation((async function* () {
      yield { type: 'progress', stage: 'querying_data', label: 'Querying TEMPO data' }
      yield { type: 'done', response: {
        request_id: 'r1', session_id: 's1', status: 'SUCCESS', provider: 'qwen', model: 'qwen-model', strategy: 'governed',
        answer: { direct_answer: 'Rp10', executive_summary: 'Total Rp10', insights: [], business_implications: [], caveats: [], data_reference: 'result', chart_spec: { type: 'kpi', title: 'Total Sales', y: 'value' } },
        data: { columns: ['value'], rows: [{ value: 10 }], row_count: 1, execution_ms: 1 }, chart_spec: { type: 'kpi', title: 'Total Sales', y: 'value' },
        timings: { context_ms: 1, planning_ms: 1, validation_ms: 1, query_ms: 1, analysis_ms: 1, total_ms: 6 }, retry_count: 0,
      } }
    }) as never)
    render(<ModelSelectionProvider><AskDataPage /></ModelSelectionProvider>)

    fireEvent.click(await screen.findByRole('button', { name: 'Random Question' }))
    expect(await screen.findByDisplayValue('Berapa total Gross Billing Value?')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await screen.findByText('Total Rp10')
    screen.getByText('Total Sales')
    await waitFor(() => expect(api.chatStream).toHaveBeenCalledWith(
      'Berapa total Gross Billing Value?',
      expect.any(String),
      { provider: 'qwen', model: 'qwen-model' },
      expect.any(AbortSignal),
    ))
  })

  it('presents the direct answer, implications, and data reference with clear hierarchy', async () => {
    vi.mocked(api.models).mockResolvedValue({ models: [{ provider: 'qwen', id: 'qwen-model', label: 'Qwen Private', available: true, reason: null }] })
    vi.mocked(api.chatStream).mockImplementation((async function* () {
      yield { type: 'done', response: {
        request_id: 'r2', session_id: 's2', status: 'SUCCESS', provider: 'qwen', model: 'qwen-model', strategy: 'governed',
        answer: { direct_answer: 'Gross Sales Q4 sebesar Rp10 miliar.', executive_summary: 'Nilai ini merupakan akumulasi Oktober–Desember.', insights: ['Desember tertinggi.'], business_implications: ['Prioritaskan ketersediaan stok Desember.'], caveats: ['Data hanya Q4 2024.'], data_reference: 'gold.rpt_sap_monthly_executive_semantic', chart_spec: null },
        data: { columns: [], rows: [], row_count: 0, execution_ms: 1 }, chart_spec: null,
        timings: { context_ms: 1, planning_ms: 1, validation_ms: 1, query_ms: 1, analysis_ms: 1, total_ms: 6 }, retry_count: 0,
      } }
    }) as never)
    render(<ModelSelectionProvider><AskDataPage /></ModelSelectionProvider>)

    fireEvent.change(screen.getByPlaceholderText('Ask a commercial question...'), { target: { value: 'Berapa gross sales Q4?' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Send question' }))

    const directAnswer = await screen.findByText('Gross Sales Q4 sebesar Rp10 miliar.')
    expect(directAnswer.className).toContain('font-semibold')
    screen.getByText('Business implications')
    screen.getByText('Prioritaskan ketersediaan stok Desember.')
    screen.getByText('gold.rpt_sap_monthly_executive_semantic')
  })

  it('toggles the navigation and conversation sidebars together for full-screen chat', async () => {
    vi.mocked(api.models).mockResolvedValue({ models: [{ provider: 'qwen', id: 'qwen-model', label: 'Qwen Private', available: true, reason: null }] })
    render(<AppShell><ModelSelectionProvider><AskDataPage /></ModelSelectionProvider></AppShell>)

    const navigation = screen.getByLabelText('Primary sidebar')
    const history = screen.getByLabelText('Conversation history sidebar')
    expect(navigation.getAttribute('aria-hidden')).toBe('false')
    expect(history.getAttribute('aria-hidden')).toBe('false')

    fireEvent.click(screen.getByRole('button', { name: 'Enter full screen chat' }))

    expect(navigation.getAttribute('aria-hidden')).toBe('true')
    expect(history.getAttribute('aria-hidden')).toBe('true')
    expect(navigation.hasAttribute('inert')).toBe(true)
    expect(history.hasAttribute('inert')).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Exit full screen chat' }))
    expect(navigation.getAttribute('aria-hidden')).toBe('false')
    expect(history.getAttribute('aria-hidden')).toBe('false')
    expect(navigation.hasAttribute('inert')).toBe(false)
    expect(history.hasAttribute('inert')).toBe(false)
  })

  it('lets the user stop a request that is still loading', async () => {
    vi.mocked(api.models).mockResolvedValue({ models: [{ provider: 'qwen', id: 'qwen-model', label: 'Qwen Private', available: true, reason: null }] })
    vi.mocked(api.chatStream).mockImplementation((async function* (_question, _session, _selection, signal?: AbortSignal) {
      yield { type: 'progress', stage: 'querying_data', label: 'Querying TEMPO data' }
      await new Promise<void>((_resolve, reject) => signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }))
    }) as never)
    render(<ModelSelectionProvider><AskDataPage /></ModelSelectionProvider>)

    fireEvent.change(screen.getByPlaceholderText('Ask a commercial question...'), { target: { value: 'Berapa fill rate?' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Send question' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Stop request' }))

    await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop request' })).toBeNull())
    expect(screen.getByText('Request stopped.')).toBeTruthy()
  })

  it('times out a request and clears its loading state after 90 seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(api.models).mockResolvedValue({ models: [{ provider: 'qwen', id: 'qwen-model', label: 'Qwen Private', available: true, reason: null }] })
    vi.mocked(api.chatStream).mockImplementation((async function* (_question, _session, _selection, signal?: AbortSignal) {
      yield { type: 'progress', stage: 'querying_data', label: 'Querying TEMPO data' }
      await new Promise<void>((_resolve, reject) => signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }))
    }) as never)
    render(<ModelSelectionProvider><AskDataPage /></ModelSelectionProvider>)

    fireEvent.change(screen.getByPlaceholderText('Ask a commercial question...'), { target: { value: 'Berapa fill rate?' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Send question' }))
    await screen.findByRole('button', { name: 'Stop request' })
    await act(async () => { await vi.advanceTimersByTimeAsync(90_000) })

    expect(screen.queryByRole('button', { name: 'Stop request' })).toBeNull()
    expect(screen.getByText('Request timed out. Please try again.')).toBeTruthy()
  })
})
