'use client'

import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { MessageSquareText, MoreHorizontal, Pin, PinOff, Trash2 } from 'lucide-react'
import type { ChatSession } from '../lib/chatSessions'

export type ConversationSessionListProps = {
  sessions: ChatSession[]
  activeSessionId: string
  collapsed?: boolean
  onOpenSession: (session: ChatSession) => void
  onRemoveSession: (event: MouseEvent, id: string) => void
  onTogglePinSession: (event: MouseEvent, id: string) => void
}

export function ConversationSessionList({
  sessions,
  activeSessionId,
  collapsed = false,
  onOpenSession,
  onRemoveSession,
  onTogglePinSession,
}: ConversationSessionListProps) {
  const [menuSessionId, setMenuSessionId] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuSessionId) return
    function onPointerDown(event: PointerEvent) {
      const target = event.target
      if (!(target instanceof Node) || !listRef.current?.contains(target)) {
        setMenuSessionId(null)
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuSessionId(null)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuSessionId])

  if (collapsed) return null

  return (
    <div ref={listRef} className="mt-1 min-h-0 flex-1 overflow-y-auto">
      <div className="type-sidebar-section mt-4 px-1">Recent</div>
      {sessions.length ? (
        <ul className="mt-2 space-y-0.5">
          {sessions.map(session => {
            const active = session.id === activeSessionId
            const menuOpen = menuSessionId === session.id
            return (
              <li key={session.id} className="group relative">
                <button
                  type="button"
                  title={session.title}
                  onClick={() => {
                    setMenuSessionId(null)
                    onOpenSession(session)
                  }}
                  className={`type-session-title flex h-9 w-full items-center gap-2 rounded-lg pl-2 pr-9 text-left transition-colors ${
                    active ? 'bg-violet-50 text-cloudera-violet' : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <MessageSquareText size={14} className="shrink-0 opacity-70" />
                  <span className="min-w-0 flex-1 truncate">{session.title}</span>
                  {session.pinned ? <Pin size={12} className="shrink-0 opacity-60" aria-hidden /> : null}
                </button>
                <div className="absolute right-0.5 top-1/2 z-10 -translate-y-1/2">
                  <button
                    type="button"
                    aria-label="Conversation options"
                    aria-expanded={menuOpen}
                    aria-haspopup="menu"
                    className={`rounded-md p-1 text-slate-400 transition-opacity hover:bg-white hover:text-slate-700 ${
                      menuOpen ? 'opacity-100 bg-white text-slate-700 shadow-sm' : 'opacity-0 group-hover:opacity-100'
                    } ${active ? 'hover:bg-violet-100/80' : ''}`}
                    onClick={event => {
                      event.stopPropagation()
                      setMenuSessionId(current => (current === session.id ? null : session.id))
                    }}
                  >
                    <MoreHorizontal size={16} />
                  </button>
                  {menuOpen ? (
                    <div
                      role="menu"
                      className="absolute right-0 top-full mt-1 min-w-[10.5rem] rounded-lg border border-slate-200/90 bg-white py-1 shadow-lg"
                    >
                      <button
                        type="button"
                        role="menuitem"
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                        onClick={event => {
                          event.stopPropagation()
                          setMenuSessionId(null)
                          onTogglePinSession(event, session.id)
                        }}
                      >
                        {session.pinned ? (
                          <>
                            <PinOff size={14} className="shrink-0" />
                            Unpin
                          </>
                        ) : (
                          <>
                            <Pin size={14} className="shrink-0" />
                            Pin
                          </>
                        )}
                      </button>
                      <div className="my-1 border-t border-slate-100" role="separator" />
                      <button
                        type="button"
                        role="menuitem"
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50"
                        onClick={event => {
                          event.stopPropagation()
                          setMenuSessionId(null)
                          onRemoveSession(event, session.id)
                        }}
                      >
                        <Trash2 size={14} className="shrink-0" />
                        Delete
                      </button>
                    </div>
                  ) : null}
                </div>
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
