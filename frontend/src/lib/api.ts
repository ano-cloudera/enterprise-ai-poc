import type { ChatResponse, DashboardOverview, DashboardState } from '../types/api'
import { validateChatResponse } from './contract'

// Always same-origin from the browser's perspective, even in the split
// deployment (Backend as its own CAI Application). Cross-origin fetch()
// from the browser to the Backend's own domain depends on CORS being
// allowed by CAI's gateway (Istio), which is platform-level infrastructure
// outside this application's control and was observed to reject every
// origin regardless of the app-level CORS_ORIGINS setting. Instead,
// next.config.mjs's server-side rewrite proxies /api/:path* to
// BACKEND_API_URL (a plain, non-NEXT_PUBLIC_ server env var) — the browser
// never sees a second domain, so there is nothing for a browser CORS
// policy to block.
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

export const api = {
  publicConfig: () => request<any>('/config/public'),
  semanticCapabilities: () => request<any>('/semantic/capabilities'),
  settings: () => request<any>('/settings'),
  updateSettings: (body: unknown) => request<any>('/settings', { method: 'PUT', body: JSON.stringify(body) }),
  dashboard: (context: DashboardState) => request<DashboardOverview>('/dashboard/overview', { method: 'POST', body: JSON.stringify({ context: dashboardContext(context) }) }),
  monitoring: () => request<any>('/monitoring/summary'),
  chat: async (
    question: string,
    sessionId: string,
    dashboardState: DashboardState,
  ) => validateChatResponse(await request<unknown>('/chat', {
    method: 'POST',
    body: JSON.stringify({
      question,
      session_id: sessionId,
      language: 'auto',
      context: dashboardContext(dashboardState),
    }),
  })),
  // SSE version of chat() for the agent_studio backend's much longer
  // multi-agent chain: yields {type: 'progress', label} frames while the
  // answer is worked on, then one {type: 'done', response: ChatResponse}.
  // Uses fetch()+ReadableStream (not EventSource, which can't POST) so the
  // question/session/context body matches chat()'s exactly.
  chatStream: async function* (
    question: string,
    sessionId: string,
    dashboardState: DashboardState,
  ): AsyncGenerator<{ type: 'progress'; label: string } | { type: 'done'; response: ChatResponse }> {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        session_id: sessionId,
        language: 'auto',
        context: dashboardContext(dashboardState),
      }),
    })
    if (!response.ok || !response.body) throw new Error(`${response.status} ${response.statusText}`)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    // Processes every frame currently in `buffer` (used both per network
    // chunk and once more after the stream ends, in case the final chunk
    // arrived in the same read() as done: true — reader.read() can report
    // done alongside data rather than only after an empty final read, so a
    // naive "break on done" loses whatever was still unflushed in buffer,
    // including the terminal {type: "done"} frame itself).
    function* drain(flushRemainder: boolean) {
      const frames = buffer.split('\n\n')
      buffer = flushRemainder ? '' : (frames.pop() ?? '')
      for (const frame of frames) {
        const line = frame.split('\n').find(l => l.startsWith('data: '))
        if (!line) continue
        const payload = JSON.parse(line.slice('data: '.length))
        if (payload.type === 'done') {
          yield { type: 'done' as const, response: validateChatResponse(payload.response) }
        } else if (payload.type === 'progress') {
          yield { type: 'progress' as const, label: payload.label }
        }
      }
    }
    while (true) {
      const { done, value } = await reader.read()
      if (value) buffer += decoder.decode(value, { stream: true })
      yield* drain(done)
      if (done) return
    }
  },
}

function dashboardContext(state: DashboardState) {
  const { chat: _, ...context } = state
  return context
}
