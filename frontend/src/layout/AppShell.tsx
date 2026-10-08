'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { BarChart3, Bot, Download, PanelLeftClose, PanelLeftOpen, Plus, Settings } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { BrandMark } from '../components/BrandMark'
import { ConversationSessionList, type ConversationSessionListProps } from '../components/ConversationSessionList'
import { appConfig } from '../config/appConfig'

const navigation = [
  { href: '/', label: appConfig.navigationAskData, icon: Bot },
  { href: '/usage', label: appConfig.navigationUsage, icon: BarChart3 },
  { href: '/settings', label: appConfig.navigationSettings, icon: Settings },
]

/** Collapsed sidebar: one footprint for logo, toggle, New Chat, and nav icons. */
const COLLAPSED_RAIL_ITEM =
  'grid h-10 w-10 shrink-0 place-items-center rounded-xl transition-colors'

export type ChatSessionSidebarState = Omit<ConversationSessionListProps, 'collapsed'> & {
  onNewChat: () => void
}

export type ChatPageChromeState = {
  showDownload: boolean
  downloadingPdf: boolean
  loading: boolean
  onDownloadPdf: () => void
  /** Hide top header title (e.g. empty Ask Data) so branding stays in the conversation area. */
  minimalHeader?: boolean
}

type ChatLayoutState = {
  sidebarCollapsed: boolean
  toggleSidebarCollapsed: () => void
  chatSessionSidebar: ChatSessionSidebarState | null
  setChatSessionSidebar: (state: ChatSessionSidebarState | null) => void
  chatPageChrome: ChatPageChromeState | null
  setChatPageChrome: (state: ChatPageChromeState | null) => void
}

const ChatLayoutContext = createContext<ChatLayoutState>({
  sidebarCollapsed: false,
  toggleSidebarCollapsed: () => undefined,
  chatSessionSidebar: null,
  setChatSessionSidebar: () => undefined,
  chatPageChrome: null,
  setChatPageChrome: () => undefined,
})

export function useChatLayout() {
  return useContext(ChatLayoutContext)
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [chatSessionSidebar, setChatSessionSidebarState] = useState<ChatSessionSidebarState | null>(null)
  const [chatPageChrome, setChatPageChromeState] = useState<ChatPageChromeState | null>(null)

  const toggleSidebarCollapsed = useCallback(() => {
    setSidebarCollapsed(current => !current)
  }, [])

  const setChatSessionSidebar = useCallback((state: ChatSessionSidebarState | null) => {
    setChatSessionSidebarState(state)
  }, [])

  const setChatPageChrome = useCallback((state: ChatPageChromeState | null) => {
    setChatPageChromeState(state)
  }, [])

  const layoutValue = useMemo(
    () => ({
      sidebarCollapsed,
      toggleSidebarCollapsed,
      chatSessionSidebar,
      setChatSessionSidebar,
      chatPageChrome,
      setChatPageChrome,
    }),
    [sidebarCollapsed, toggleSidebarCollapsed, chatSessionSidebar, setChatSessionSidebar, chatPageChrome, setChatPageChrome],
  )

  const onAskData = pathname === '/'
  const showChatWorkspace = onAskData && chatSessionSidebar !== null
  const sidebarExpandedClass = sidebarCollapsed ? 'lg:w-[68px]' : 'lg:w-[272px]'
  const mainPadClass = sidebarCollapsed ? 'lg:pl-[68px]' : 'lg:pl-[272px]'

  return (
    <ChatLayoutContext.Provider value={layoutValue}>
      <div className="min-h-screen bg-cloudera-mist text-cloudera-ink">
        <aside
          aria-label="Primary sidebar"
          className={`fixed inset-y-0 left-0 z-30 hidden ${sidebarExpandedClass} flex-col border-r border-slate-200 bg-white transition-[width] duration-300 ease-in-out lg:flex`}
        >
          <div
            className={`flex shrink-0 border-b border-slate-100 ${
              sidebarCollapsed
                ? 'flex-col items-center gap-2 px-2 py-3'
                : 'items-center justify-between gap-2 px-3 py-3'
            }`}
          >
            {!sidebarCollapsed ? (
              <div className="min-w-0 flex-1">
                <BrandMark />
              </div>
            ) : (
              <div
                className={`${COLLAPSED_RAIL_ITEM} border border-slate-100 bg-white shadow-[0_1px_3px_rgba(36,19,95,0.06)]`}
              >
                <img
                  src={appConfig.branding.logo}
                  alt=""
                  aria-hidden
                  className="h-7 w-7 object-contain"
                />
              </div>
            )}
            <button
              type="button"
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-expanded={!sidebarCollapsed}
              onClick={toggleSidebarCollapsed}
              className={
                sidebarCollapsed
                  ? `${COLLAPSED_RAIL_ITEM} border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-cloudera-navy`
                  : `${COLLAPSED_RAIL_ITEM} text-slate-500 hover:bg-slate-50 hover:text-cloudera-navy`
              }
            >
              {sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            </button>
          </div>

          <div
            className={`flex min-h-0 flex-1 flex-col ${
              sidebarCollapsed ? 'items-center gap-1.5 px-2 py-3' : 'px-3 py-3'
            }`}
          >
            {showChatWorkspace && (
              <button
                type="button"
                aria-label="New chat"
                title="New chat"
                onClick={chatSessionSidebar.onNewChat}
                className={
                  sidebarCollapsed
                    ? `${COLLAPSED_RAIL_ITEM} bg-cloudera-orange text-white hover:brightness-95`
                    : 'btn-primary mb-4 h-11 w-full text-sm'
                }
              >
                <Plus size={sidebarCollapsed ? 18 : 16} />
                {!sidebarCollapsed && <span>New Chat</span>}
              </button>
            )}

            <nav
              aria-label="Primary navigation"
              className={sidebarCollapsed ? 'flex flex-col items-center gap-1.5' : 'space-y-0.5'}
            >
              {!sidebarCollapsed && (
                <div className="type-sidebar-section mb-2 px-1">Navigation</div>
              )}
              {navigation.map(item => {
                const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={item.label}
                    className={`type-sidebar-nav transition-colors ${
                      sidebarCollapsed
                        ? `${COLLAPSED_RAIL_ITEM} ${
                            active
                              ? 'bg-violet-50 font-semibold text-cloudera-violet'
                              : 'text-slate-600 hover:bg-slate-50'
                          }`
                        : `flex h-11 items-center gap-2 rounded-xl px-2 ${
                            active
                              ? 'bg-violet-50 font-semibold text-cloudera-violet'
                              : 'text-slate-600 hover:bg-slate-50'
                          }`
                    }`}
                  >
                    {sidebarCollapsed ? (
                      <Icon size={18} />
                    ) : (
                      <>
                        <span className="grid h-8 w-8 shrink-0 place-items-center">
                          <Icon size={18} />
                        </span>
                        {item.label}
                      </>
                    )}
                  </Link>
                )
              })}
            </nav>

            {showChatWorkspace && chatSessionSidebar && (
              <ConversationSessionList
                collapsed={sidebarCollapsed}
                sessions={chatSessionSidebar.sessions}
                activeSessionId={chatSessionSidebar.activeSessionId}
                onOpenSession={chatSessionSidebar.onOpenSession}
                onRemoveSession={chatSessionSidebar.onRemoveSession}
                onTogglePinSession={chatSessionSidebar.onTogglePinSession}
              />
            )}
          </div>

          {!sidebarCollapsed && (
            <div className="shrink-0 border-t border-slate-100 px-3 py-3">
              <div className="flex items-center gap-2">
                <img
                  src="/cloudera-logo.png"
                  alt=""
                  aria-hidden
                  className="h-5 w-5 shrink-0 rounded object-contain"
                />
                <span className="text-xs font-medium text-slate-600">{appConfig.sidebarPoweredByLabel}</span>
              </div>
              {appConfig.sidebarFooterCaption ? (
                <p className="type-chat-meta mt-1.5 leading-snug">{appConfig.sidebarFooterCaption}</p>
              ) : null}
            </div>
          )}
        </aside>

        <div className={`flex min-h-screen flex-col transition-[padding-left] duration-300 ease-in-out ${mainPadClass}`} style={{ minHeight: '100dvh' }}>
          <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 sm:px-5">
            {onAskData && chatPageChrome?.minimalHeader ? (
              <div className="min-w-0 flex-1" aria-hidden />
            ) : (
              <div className="type-app-title min-w-0 truncate">{appConfig.headerTitle}</div>
            )}
            <div className="flex shrink-0 items-center gap-2">
              <div className="chip py-1">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Database
              </div>
              {onAskData && chatPageChrome?.showDownload && (
                <button
                  type="button"
                  aria-label="Download conversation as PDF"
                  disabled={chatPageChrome.downloadingPdf || chatPageChrome.loading}
                  onClick={chatPageChrome.onDownloadPdf}
                  className="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 px-2 text-xs font-semibold text-slate-600 transition-colors hover:border-cloudera-orange/40 hover:bg-orange-50/50 disabled:opacity-50"
                >
                  <Download size={14} />
                  <span className="hidden md:inline">{chatPageChrome.downloadingPdf ? 'PDF…' : 'PDF'}</span>
                </button>
              )}
            </div>
          </header>
          <main className={`min-h-0 flex-1 ${onAskData ? 'flex min-h-0 flex-col' : 'p-4 sm:p-6'}`}>{children}</main>
        </div>

        <nav aria-label="Mobile navigation" className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t border-slate-200 bg-white p-2 lg:hidden">
          {navigation.map(item => (
            <Link key={item.href} href={item.href} className="flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold text-cloudera-navy">
              <item.icon size={16} />
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </ChatLayoutContext.Provider>
  )
}
