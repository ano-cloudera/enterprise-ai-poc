import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../lib/api'
import { ModelSelectionProvider } from '../lib/modelSelection'
import { AskDataPage } from './AskDataPage'

vi.mock('../lib/api', () => ({ api: { models: vi.fn(), randomQueries: vi.fn(), chatStream: vi.fn() } }))

describe('V2 Ask Data page', () => {
  afterEach(cleanup)

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
    await waitFor(() => expect(api.chatStream).toHaveBeenCalledWith('Berapa total Gross Billing Value?', expect.any(String), { provider: 'qwen', model: 'qwen-model' }))
  })
})
