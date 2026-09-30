import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../lib/api'
import { ModelSelectionProvider, useModelSelection } from '../lib/modelSelection'
import { SettingsPage } from './SettingsPage'

vi.mock('../lib/api', () => ({ api: { models: vi.fn() } }))

function SelectionProbe() {
  const value = useModelSelection()
  return <output>{value.selection ? `${value.selection.provider}:${value.selection.model}` : 'none'}</output>
}

describe('V2 Settings', () => {
  afterEach(cleanup)

  it('uses backend discovery and disables unavailable models', async () => {
    vi.mocked(api.models).mockResolvedValue({ models: [
      { provider: 'qwen', id: 'qwen-configured', label: 'Qwen Private', available: true, reason: null },
      { provider: 'gemini', id: 'gemini-configured', label: 'Gemini', available: false, reason: 'API key not configured' },
      { provider: 'openai', id: 'gpt-configured', label: 'ChatGPT', available: true, reason: null },
    ] })
    render(<ModelSelectionProvider><SettingsPage /><SelectionProbe /></ModelSelectionProvider>)

    const selector = await screen.findByLabelText('Active model')
    expect((screen.getByRole('option', { name: /Gemini/ }) as HTMLOptionElement).disabled).toBe(true)
    fireEvent.change(selector, { target: { value: 'openai::gpt-configured' } })

    await waitFor(() => screen.getByText('openai:gpt-configured'))
  })
})
