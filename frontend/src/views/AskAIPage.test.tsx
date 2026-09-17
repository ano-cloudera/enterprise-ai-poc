import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AskAIPage } from './AskAIPage'
import { api } from '../lib/api'

const dashboardState = {
  filters: { region: ['Jawa Barat'], product: [], category: [], channel: [], outlet: [], customer_segment: [] },
  date_range: { preset: 'current_month', start: null, end: null },
  metric: 'net_sales', dimension: 'region', highlights: [], ai_applied_context: [], revision: 0,
  chat: { chart: null, table: { visible: true, columns: [] } },
}
const stateActions = { applyActions: vi.fn(), removeAppliedContext: vi.fn(), reset: vi.fn() }
const scrollIntoView = vi.fn()

const response = {
  status: 'ok', question: 'Kenapa sales turun?',
  answer: {
    summary: 'Nilai Jawa Barat berubah 18.21664440535221% dari 32568.457000000002 menjadi 38501.337000000004.',
    drivers: [
      'General Trade menjadi kontributor utama. Evidence: current_value=38501.337000000004',
      'Bodrex menjadi produk utama.', 'Distribusi perlu diperiksa.', 'Driver keempat tidak boleh tampil.',
    ],
    recommended_actions: ['Review product drivers', 'Compare channels', 'Track recovery', 'Fourth action'], caveats: [],
  },
  data: { columns: ['region', 'current_value', 'percentage_change'], rows: [{ region: 'Jawa Barat', current_value: 38501.337000000004, percentage_change: 18.21664440535221 }] },
  chart_spec: null,
  ui_actions: [],
  metadata: { trace_id: 'secret-trace', session_id: 'developer-session', intent: 'analytical', resolved_context: dashboardState, execution_time_ms: 123 },
} as const

vi.mock('../lib/api', () => ({ api: { chat: vi.fn() } }))
vi.mock('../lib/project', () => ({ useProject: () => ({ config: { project_name: 'Tempo Scan Commercial Intelligence Assistant' } }) }))
vi.mock('../lib/dashboardState', () => ({ useDashboardState: () => ({ state: dashboardState, ...stateActions }) }))
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams() }))

describe('Ask AI business UX', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })
    vi.mocked(api.chat).mockResolvedValue(response as never)
  })
  afterEach(cleanup)

  it('keeps the initial chat focused by hiding context, follow-ups, and technical side panels', () => {
    const { container } = render(<AskAIPage />)
    expect(screen.queryByText(/Governed AI Workspace/i)).toBeNull()
    screen.getByText('Governed Data')
    expect(container.textContent).not.toMatch(/Current Context|Shared with the dashboard|Suggested Follow-ups|Resolved Context|How it works|Controlled workflow|Trusted SQL|Demo session|current_month|net_sales|Technical trace|Trace ID|Session ID/)
  })

  it('gives the conversation more room and centers the empty state within the panel', () => {
    render(<AskAIPage />)
    const recentHeading = screen.getByText('Recent conversations')
    const layout = recentHeading.closest('aside')?.parentElement
    const emptyState = screen.getByRole('heading', { name: 'Ask your commercial data' }).parentElement
    const conversation = screen.getByRole('log', { name: 'Conversation' })

    expect(layout?.className).toContain('xl:grid-cols-[214px_minmax(0,1fr)]')
    expect(emptyState?.className).toContain('max-w-3xl')
    expect(emptyState?.className).toContain('m-auto')
    expect(conversation.className).toContain('flex')
    expect(recentHeading.className).toContain('text-sm')
    expect(screen.getByText('SCAN').className).toContain('text-sm')
  })

  it('keeps the composer outside a viewport-bounded scrolling conversation', () => {
    render(<AskAIPage />)
    const conversation = screen.getByRole('log', { name: 'Conversation' })
    const composer = screen.getByPlaceholderText('Ask a follow-up question...')
    const chatShell = conversation.closest('section')

    expect(conversation.className).toContain('min-h-0')
    expect(conversation.className).toContain('overflow-y-auto')
    expect(chatShell?.className.split(' ')).toContain('h-full')
    expect(conversation.contains(composer)).toBe(false)
  })

  it('moves the conversation to the newest response automatically', async () => {
    render(<AskAIPage />)
    scrollIntoView.mockClear()
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Kenapa sales turun?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await screen.findByLabelText('AI response')
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled())
  })

  it('renders a concise formatted answer, evidence table, and contextual follow-ups', async () => {
    const { container } = render(<AskAIPage />)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Kenapa sales turun?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await screen.findByText('Executive Summary')
    screen.getByText('Nilai Jawa Barat berubah +18.2% dari Rp32.57B menjadi Rp38.50B.')
    screen.getByText('Rp38.50B')
    screen.getByText('+18.2%')
    const answer = screen.getByLabelText('AI response')
    within(answer).getByRole('group', { name: 'Suggested follow-up questions' })
    within(answer).getByText('Which products drove the decline?')
    expect(screen.queryByText('Driver keempat tidak boleh tampil.')).toBeNull()
    expect(screen.queryByText('Fourth action')).toBeNull()
    expect(container.textContent).not.toMatch(/current_value=|secret-trace|developer-session|18\.21664440535221|38501\.337000000004/)
  })

  it('sends a selected response follow-up immediately', async () => {
    render(<AskAIPage />)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Kenapa sales turun?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    const answer = await screen.findByLabelText('AI response')
    fireEvent.click(within(answer).getByRole('button', { name: 'Which products drove the decline?' }))

    await waitFor(() => expect(api.chat).toHaveBeenCalledTimes(2))
    expect(api.chat).toHaveBeenLastCalledWith('Which products drove the decline?', expect.any(Array), expect.anything())
  })

  it('submits with Enter, keeps Shift+Enter multiline, and ignores empty Enter', async () => {
    render(<AskAIPage />)
    const input = screen.getByPlaceholderText('Ask a follow-up question...') as HTMLTextAreaElement
    expect(fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })).toBe(true)
    expect(api.chat).not.toHaveBeenCalled()

    fireEvent.change(input, { target: { value: 'Bandingkan Bodrex' } })
    expect(fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })).toBe(true)
    expect(api.chat).not.toHaveBeenCalled()
    fireEvent.change(input, { target: { value: 'Bandingkan Bodrex\ndengan kompetitor' } })
    expect(input.value).toContain('\n')

    expect(fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })).toBe(false)
    await waitFor(() => expect(api.chat).toHaveBeenCalledTimes(1))
  })

  it('prevents duplicate submissions and keeps the send button functional', async () => {
    let resolveRequest: (value: unknown) => void = () => undefined
    vi.mocked(api.chat).mockImplementation(() => new Promise(resolve => { resolveRequest = resolve }) as never)
    render(<AskAIPage />)
    const input = screen.getByPlaceholderText('Ask a follow-up question...')
    fireEvent.change(input, { target: { value: 'Forecast Bodrex' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await screen.findByText('Analyzing governed data...')
    expect((screen.getByRole('button', { name: 'Send question' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(api.chat).toHaveBeenCalledTimes(1)
    resolveRequest(response)
    await screen.findByText('Executive Summary')
  })

  it('shows a safe business error without backend details', async () => {
    vi.mocked(api.chat).mockRejectedValue(new Error('500 traceback secret'))
    render(<AskAIPage />)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Question' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await screen.findByText('Unable to complete the analysis right now. Please try again.')
    expect(screen.queryByText(/traceback secret/)).toBeNull()
  })
})
