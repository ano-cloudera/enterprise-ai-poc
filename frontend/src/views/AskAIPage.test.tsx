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
const stateActions = { applyDashboardAiActions: vi.fn(), removeAppliedContext: vi.fn(), reset: vi.fn() }
const scrollIntoView = vi.fn()
const projectConfig = {
  project_name: 'Tempo Scan Commercial Intelligence Assistant',
  semantic_capabilities_enabled: false,
}

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
  ui_actions: [{ type: 'SHOW_TABLE', target: 'chat', value: { columns: ['region', 'current_value', 'percentage_change'] } }],
  metadata: { trace_id: 'secret-trace', session_id: 'developer-session', intent: 'analytical', resolved_context: dashboardState, execution_time_ms: 123 },
} as const

vi.mock('../lib/api', () => ({ api: { chat: vi.fn(), semanticCapabilities: vi.fn() } }))
vi.mock('../lib/project', () => ({ useProject: () => ({ config: projectConfig }) }))
vi.mock('../lib/dashboardState', () => ({ useDashboardState: () => ({ state: dashboardState, ...stateActions }) }))
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams() }))

describe('Ask AI business UX', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    projectConfig.semantic_capabilities_enabled = false
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })
    vi.mocked(api.chat).mockResolvedValue(response as never)
    vi.mocked(api.semanticCapabilities).mockResolvedValue({ examples: [] } as never)
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

  it('shows governed Q4 capabilities only for the opt-in Impala profile', async () => {
    projectConfig.semantic_capabilities_enabled = true
    vi.mocked(api.semanticCapabilities).mockResolvedValue({
      examples: ['Bagaimana tren Gross Sales selama Q4 2024?'],
    } as never)
    render(<AskAIPage />)

    await screen.findByRole('heading', { name: 'Ask SCAN about TEMPO Q4 2024' })
    screen.getByText('Impala · Q4 2024')
    screen.getByText('Bagaimana tren Gross Sales selama Q4 2024?')
    expect(api.semanticCapabilities).toHaveBeenCalledOnce()
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
    expect(api.chat).toHaveBeenLastCalledWith('Which products drove the decline?', expect.any(String), expect.anything())
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

  it('renders a conversational answer as plain text without the Executive Summary card', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      ...response,
      answer: { summary: 'Ya, saya bisa berkomunikasi dalam Bahasa Indonesia.', drivers: [], recommended_actions: [], caveats: [] },
      metadata: { ...response.metadata, intent: 'conversational' },
    } as never)
    render(<AskAIPage />)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'bisa bahasa indonesia?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await screen.findByText('Ya, saya bisa berkomunikasi dalam Bahasa Indonesia.')
    expect(screen.queryByText('Executive Summary')).toBeNull()
    expect(screen.queryByRole('group', { name: 'Suggested follow-up questions' })).toBeNull()
  })

  it('renders answer caveats so a governance/data-availability disclaimer actually reaches the user', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      ...response,
      answer: { ...response.answer, caveats: ['All data access stays within the governed dataset; nothing outside it can be shown.'] },
    } as never)
    render(<AskAIPage />)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Kenapa sales turun?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await screen.findByText('All data access stays within the governed dataset; nothing outside it can be shown.')
  })

  it('lists the active conversation in the sidebar as soon as it has messages, without a reload', async () => {
    window.localStorage.clear()
    render(<AskAIPage />)
    screen.getByText('No conversations yet.')

    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Kenapa sales turun?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await screen.findByLabelText('AI response')

    expect(screen.queryByText('No conversations yet.')).toBeNull()
    expect(screen.getAllByText('Kenapa sales turun?').length).toBeGreaterThan(1)
  })

  it('keeps each answer\'s own table columns even after a later question uses different columns', async () => {
    const channelResponse = {
      ...response,
      data: { columns: ['channel', 'value'], rows: [{ channel: 'Modern Trade', value: 1000 }] },
      ui_actions: [{ type: 'SHOW_TABLE', target: 'chat', value: { columns: ['channel', 'value'] } }],
    }
    const regionResponse = {
      ...response,
      data: { columns: ['region', 'value'], rows: [{ region: 'Jawa Barat', value: 2000 }] },
      ui_actions: [{ type: 'SHOW_TABLE', target: 'chat', value: { columns: ['region', 'value'] } }],
    }
    vi.mocked(api.chat).mockResolvedValueOnce(channelResponse as never).mockResolvedValueOnce(regionResponse as never)

    render(<AskAIPage />)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Breakdown by channel' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await screen.findByText('Modern Trade')

    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Sales per region' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await screen.findByText('Jawa Barat')

    // The first answer's table must still show its own "Channel" column
    // and value, not the second answer's "Region" header/data.
    screen.getByText('Modern Trade')
    expect(screen.queryByText('—')).toBeNull()
  })

  it('deletes a saved conversation from the sidebar without opening it', async () => {
    window.localStorage.clear()
    render(<AskAIPage />)
    fireEvent.change(screen.getByPlaceholderText('Ask a follow-up question...'), { target: { value: 'Kenapa sales turun?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await screen.findByLabelText('AI response')

    cleanup()
    render(<AskAIPage />)
    screen.getByText('Kenapa sales turun?')
    fireEvent.click(screen.getByRole('button', { name: 'Delete conversation' }))

    expect(screen.queryByText('Kenapa sales turun?')).toBeNull()
    screen.getByText('No conversations yet.')
  })
})
