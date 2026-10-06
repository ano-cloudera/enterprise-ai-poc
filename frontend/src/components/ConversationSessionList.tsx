'use client'

import type { MouseEvent } from 'react'
import { MessageSquareText, Trash2 } from 'lucide-react'
import type { ChatSession } from '../lib/chatSessions'

export type ConversationSessionListProps = {
  sessions: ChatSession[]
  activeSessionId: string
  collapsed?: boolean
  onOpenSession: (session: ChatSession) => void
  onRemoveSession: (event: MouseEvent, id: string) => void
}

export function ConversationSessionList({
  sessions,
  activeSessionId,
  collapsed = false,
  onOpenSession,
  onRemoveSession,
}: ConversationSessionListProps) {
  if (collapsed) return null

  return (
    <div className="mt-1 min-h-0 flex-1 overflow-y-auto">
      <div className="type-sidebar-section mt-4 px-1">Recent</div>
      {sessions.length ? (
        <ul className="mt-2 space-y-0.5">
          {sessions.map(session => {
            const active = session.id === activeSessionId
            return (
              <li key={session.id} className="group relative">
                <button
                  type="button"
                  title={session.title}
                  onClick={() => onOpenSession(session)}
                  className={`type-session-title flex h-9 w-full items-center gap-2 rounded-lg pl-2 pr-8 text-left transition-colors ${
                    active ? 'bg-violet-50 text-cloudera-violet' : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <MessageSquareText size={14} className="shrink-0 opacity-70" />
                  <span className="truncate">{session.title}</span>
                </button>
                <button
                  type="button"
                  aria-label="Delete conversation"
                  className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 opacity-0 transition-opacity hover:bg-white hover:text-rose-600 group-hover:opacity-100"
                  onClick={event => onRemoveSession(event, session.id)}
                >
                  <Trash2 size={12} />
                </button>
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="mt-2 px-1 text-xs leading-5 text-slate-500">No conversations yet.</p>
      )}
    </div>
  )
}
