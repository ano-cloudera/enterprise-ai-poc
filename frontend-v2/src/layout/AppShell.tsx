'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Bot, Settings } from 'lucide-react'
import { createContext, useContext, useState, type ReactNode } from 'react'
import { BrandMark } from '../components/BrandMark'


const navigation = [
  { href: '/', label: 'Ask Data', icon: Bot },
  { href: '/settings', label: 'Settings', icon: Settings },
]

type ChatLayoutState = {
  fullScreenChat: boolean
  toggleFullScreenChat: () => void
}

const ChatLayoutContext = createContext<ChatLayoutState>({
  fullScreenChat: false,
  toggleFullScreenChat: () => undefined,
})

export function useChatLayout() {
  return useContext(ChatLayoutContext)
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const [fullScreenRequested, setFullScreenRequested] = useState(false)
  const fullScreenChat = pathname === '/' && fullScreenRequested
  return (
    <ChatLayoutContext.Provider value={{ fullScreenChat, toggleFullScreenChat: () => setFullScreenRequested(current => !current) }}>
    <div className="min-h-screen bg-cloudera-mist text-cloudera-ink">
      <aside aria-label="Primary sidebar" aria-hidden={fullScreenChat} inert={fullScreenChat} className={`fixed inset-y-0 left-0 z-30 hidden w-[232px] flex-col border-r border-slate-200 bg-white p-4 transition-transform duration-300 ease-in-out lg:flex ${fullScreenChat ? '-translate-x-full pointer-events-none' : 'translate-x-0'}`}>
        <BrandMark />
        <nav aria-label="Primary navigation" className="mt-7 space-y-1">
          {navigation.map(item => {
            const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)
            const Icon = item.icon
            return <Link key={item.href} href={item.href} className={`flex h-11 items-center gap-2.5 rounded-xl px-2 text-xs font-bold ${active ? 'bg-violet-50 text-cloudera-violet' : 'text-slate-600 hover:bg-slate-50'}`}><span className="grid h-8 w-8 place-items-center"><Icon size={17} /></span>{item.label}</Link>
          })}
        </nav>
        <div className="mt-auto border-t border-slate-100 pt-4"><div className="text-xs font-extrabold text-cloudera-navy">Tempo Scan V2</div><div className="mt-0.5 text-[11px] text-slate-500">Commercial Intelligence</div><div className="mt-1.5 text-[10px] text-slate-400">Powered by Cloudera AI</div></div>
      </aside>
      <div className={`transition-[padding] duration-300 ease-in-out ${fullScreenChat ? 'lg:pl-0' : 'lg:pl-[232px]'}`}>
        <header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-slate-200 bg-white/95 px-4 sm:px-8"><div><div className="text-xl font-black text-cloudera-navy">Tempo Scan Intelligence</div><div className="mt-1 text-xs text-slate-400">Tempo Scan · Ask Data V2</div></div><div className="chip">Governed Ossie + Impala</div></header>
        <main className="p-4 sm:p-6">{children}</main>
      </div>
      <nav aria-label="Mobile navigation" className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t border-slate-200 bg-white p-2 lg:hidden">{navigation.map(item => <Link key={item.href} href={item.href} className="flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold text-cloudera-navy"><item.icon size={16} />{item.label}</Link>)}</nav>
    </div>
    </ChatLayoutContext.Provider>
  )
}
