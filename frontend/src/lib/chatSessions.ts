import type { ChatResponse } from '../types/api'

export type StoredMessage = { role: 'user' | 'assistant'; content: string; response?: ChatResponse }
export type ChatSession = { id: string; title: string; updatedAt: number; messages: StoredMessage[] }

const STORAGE_KEY = 'scan.ask-ai.sessions'
const HANDOFF_KEY = 'scan.ask-ai.handoff'
const MAX_SESSIONS = 20

export function createSessionId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function loadSessions(): ChatSession[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveSession(session: ChatSession) {
  if (typeof window === 'undefined' || !session.messages.length) return
  try {
    const sessions = loadSessions().filter(item => item.id !== session.id)
    sessions.unshift(session)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)))
  } catch {
    // localStorage unavailable (private mode, quota) - session just won't persist across reloads.
  }
}

export function sessionTitle(messages: StoredMessage[]): string {
  return messages.find(message => message.role === 'user')?.content.slice(0, 80) || 'New conversation'
}

// One-shot handoff payload from the floating dashboard drawer to the full
// Ask AI page: carries the already-computed ChatResponse so the page can
// render it directly instead of re-submitting the same question to the API.
export type ChatHandoff = { question: string; response: ChatResponse }

export function setHandoff(payload: ChatHandoff) {
  if (typeof window === 'undefined') return
  try {
    window.sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(payload))
  } catch {
    // ignore
  }
}

export function takeHandoff(): ChatHandoff | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.sessionStorage.getItem(HANDOFF_KEY)
    if (!raw) return null
    window.sessionStorage.removeItem(HANDOFF_KEY)
    return JSON.parse(raw)
  } catch {
    return null
  }
}
