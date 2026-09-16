import type { ChatResponse, DashboardOverview, DashboardState } from '../types/api'
import { validateChatResponse } from './contract'

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
