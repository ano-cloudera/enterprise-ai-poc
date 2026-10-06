import type { ChatResponse, ModelInfo, ModelSelection, SuggestedQuestion } from '../types/api'


async function request<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' } })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}


export const api = {
  deleteChatSession: async (sessionId: string): Promise<void> => {
    const response = await fetch(`/api/chat/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
    if (!response.ok && response.status !== 404) {
      throw new Error(`${response.status} ${response.statusText}`)
    }
  },
  models: () => request<{ models: ModelInfo[] }>('/models'),
  randomQueries: (limit = 1) => request<{ questions: SuggestedQuestion[] }>(`/random-queries?limit=${limit}`),
  chatStream: async function* (
    question: string,
    sessionId: string,
    selection: ModelSelection,
    signal?: AbortSignal,
  ): AsyncGenerator<
    { type: 'progress'; stage: string; label: string; detail?: string | null }
    | { type: 'done'; response: ChatResponse }
  > {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: sessionId, provider: selection.provider, model: selection.model }),
      signal,
    })
    if (!response.ok || !response.body) throw new Error(`${response.status} ${response.statusText}`)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let terminalReceived = false
    function* drain(flush: boolean) {
      const frames = buffer.split('\n\n')
      buffer = flush ? '' : (frames.pop() ?? '')
      for (const frame of frames) {
        const line = frame.split('\n').find(value => value.startsWith('data: '))
        if (!line) continue
        const event = JSON.parse(line.slice(6))
        if (event.type === 'done') terminalReceived = true
        yield event
      }
    }
    while (true) {
      const { done, value } = await reader.read()
      if (value) buffer += decoder.decode(value, { stream: true })
      yield* drain(done)
      if (done) {
        if (!terminalReceived) throw new Error('Stream ended without a terminal response')
        return
      }
    }
  },
}
