import type { ChatResponse, DashboardOverview, DashboardState } from '../types/api'
import { validateChatResponse } from './contract'

// Split-deployment: the backend runs as its own CAI Application with its
// own public URL. When unset, requests stay same-origin (Milestone 7's
// single-app path, e.g. local dev via next.config.mjs rewrites).
const API_BASE_URL = (process.env.NEXT_PUBLIC_BACKEND_API_URL || '').replace(/\/+$/, '')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api${path}`, {
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
