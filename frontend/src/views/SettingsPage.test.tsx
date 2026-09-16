import React from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SettingsPage } from './SettingsPage'
import { api } from '../lib/api'

vi.mock('../lib/api', () => ({
  api: {
    settings: vi.fn(),
    updateSettings: vi.fn(),
  },
}))

describe('Settings page', () => {
  afterEach(cleanup)

  it('shows only business-facing sections and hides infrastructure details', async () => {
    vi.mocked(api.settings).mockResolvedValue({
      model_name: 'Qwen3.8-27B-AWQ',
      llm_mode: 'mock',
      language: 'auto',
      system_prompt: 'Be concise and grounded in governed data.',
      data_backend: 'duckdb',
      guardrails: 'enabled',
    })
    render(<SettingsPage />)

    await waitFor(() => screen.getByText('AI Model'))
    screen.getByText('Response Language')
    screen.getByText('General Prompt / System Instruction')

    expect(screen.queryByText('Data Connection')).toBeNull()
    expect(screen.queryByText('Guardrails')).toBeNull()
    expect(screen.queryByText(/DuckDB/i)).toBeNull()
    expect(screen.queryByText(/Trino/i)).toBeNull()
    expect(screen.queryByText(/vLLM/i)).toBeNull()
    expect(screen.queryByText(/provider-agnostic/i)).toBeNull()
    expect(screen.queryByText(/proven serving baseline/i)).toBeNull()
    expect(screen.queryByText(/Protection mode/i)).toBeNull()
    expect(screen.queryByText(/allowlist/i)).toBeNull()
    expect(screen.queryByText(/row limit/i)).toBeNull()
    expect(screen.queryByText(/prompt injection/i)).toBeNull()
  })

  it('shows plain runtime status instead of technical mode strings', async () => {
    vi.mocked(api.settings).mockResolvedValue({
      model_name: 'Qwen3.8-27B-AWQ',
      llm_mode: 'live',
      language: 'auto',
      system_prompt: '',
    })
    render(<SettingsPage />)
    await waitFor(() => screen.getByText('Connected'))
  })
})
