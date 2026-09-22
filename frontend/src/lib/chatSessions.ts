import type { ChatResponse } from '../types/api'

export type StoredMessage = { role: 'user' | 'assistant'; content: string; response?: ChatResponse }
export type ChatSession = { id: string; title: string; updatedAt: number; messages: StoredMessage[] }

const STORAGE_KEY = 'scan.ask-ai.sessions'
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

export function deleteSession(id: string) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(loadSessions().filter(item => item.id !== id)))
  } catch {
    // localStorage unavailable - nothing to clean up.
  }
}

export function sessionTitle(messages: StoredMessage[]): string {
  return messages.find(message => message.role === 'user')?.content.slice(0, 80) || 'New conversation'
}
