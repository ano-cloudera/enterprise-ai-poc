import React from 'react'
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../lib/api'
import { useModelSelection } from '../lib/modelSelection'
import { renderWithProviders } from '../test/renderWithProviders'
import { SettingsPage } from './SettingsPage'

vi.mock('../lib/api', () => ({ api: { models: vi.fn() } }))

function SelectionProbe() {
  const value = useModelSelection()
  return <output>{value.selection ? `${value.selection.provider}:${value.selection.model}` : 'none'}</output>
}

describe('V2 Settings', () => {
  afterEach(cleanup)

  it('uses one AI model selector and disables unavailable models', async () => {
    vi.mocked(api.models).mockResolvedValue({ models: [
      { provider: 'qwen', id: 'qwen-configured', label: 'Qwen Private', available: true, reason: null },
      { provider: 'gemini', id: 'gemini-configured', label: 'Gemini', available: false, reason: 'API key not configured' },
      { provider: 'openai', id: 'gpt-configured', label: 'ChatGPT', available: true, reason: null },
    ] })
    renderWithProviders(
      <>
        <SettingsPage />
        <SelectionProbe />
      </>,
    )

    const modelSelect = await screen.findByLabelText('AI Model')
    const geminiOption = within(modelSelect).getByRole('option', { name: /^Gemini$/ }) as HTMLOptionElement
    expect(geminiOption.disabled).toBe(true)

    fireEvent.change(modelSelect, { target: { value: 'openai::gpt-configured' } })
    await waitFor(() => screen.getByText('openai:gpt-configured'))
    expect(screen.getByText(/Provider: OpenAI/i)).toBeTruthy()
  })
})
