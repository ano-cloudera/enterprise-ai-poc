import { beforeEach, describe, expect, it } from 'vitest'

import { loadSessions, saveSession } from './chatSessions'

describe('chat session persistence', () => {
  beforeEach(() => localStorage.clear())

  it('persists the provider and model with the conversation', () => {
    saveSession({
      id: 'session-1', title: 'Question', updatedAt: 1,
      messages: [{ role: 'user', content: 'Question' }],
      selection: { provider: 'gemini', model: 'gemini-configured' },
    })

    expect(loadSessions()[0].selection).toEqual({ provider: 'gemini', model: 'gemini-configured' })
  })
})
