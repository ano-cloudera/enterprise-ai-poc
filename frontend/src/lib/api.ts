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
  settings: () => request<any>('/settings'),
  updateSettings: (body: unknown) => request<any>('/settings', { method: 'PUT', body: JSON.stringify(body) }),
  dashboard: (context: DashboardState) => request<DashboardOverview>('/dashboard/overview', { method: 'POST', body: JSON.stringify({ context: dashboardContext(context) }) }),
  monitoring: () => request<any>('/monitoring/summary'),
  chat: async (
    question: string,
    history: { role: 'user' | 'assistant'; content: string }[] = [],
    dashboardState: DashboardState,
  ) => validateChatResponse(await request<unknown>('/chat', {
    method: 'POST',
    body: JSON.stringify({
      question,
      session_id: 'tempo-demo',
      language: 'auto',
      history,
      context: dashboardContext(dashboardState),
    }),
  })),
}

function dashboardContext(state: DashboardState) {
  const { chat: _, ...context } = state
  return context
}
