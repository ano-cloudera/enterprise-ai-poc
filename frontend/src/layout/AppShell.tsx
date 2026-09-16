'use client'

import { useEffect, useState, type ReactNode } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Bot, ChevronLeft, ChevronRight, Clock3, Gauge, LayoutDashboard, Menu,
  Settings, ShoppingBag, X,
} from 'lucide-react'
import { BrandMark } from '../components/BrandMark'
import { useProject } from '../lib/project'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/ask-ai', label: 'Ask AI', icon: Bot },
  { to: null, label: 'Market Intelligence', icon: ShoppingBag },
  { to: '/monitoring', label: 'AI Monitoring', icon: Gauge },
  { to: '/settings', label: 'Settings', icon: Settings },
] as const

export function AppShell({ children }: { children: ReactNode }) {
  const { config } = useProject()
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [openedAt, setOpenedAt] = useState('')
  const active = (to: string | null) => Boolean(to && (to === '/' ? pathname === '/' : pathname.startsWith(to)))

  useEffect(() => setOpenedAt(formatOpenedAt(new Date())), [])

  return (
    <div className="min-h-screen overflow-x-hidden bg-cloudera-mist text-cloudera-ink">
      <aside className={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-slate-200 bg-white py-4 transition-[width] duration-200 lg:flex ${collapsed ? 'w-20 px-3' : 'w-[232px] px-4'}`}>
        <div className={collapsed ? 'flex justify-center' : 'px-1'}>{collapsed ? <CompactBrand /> : <BrandMark />}</div>
        <nav aria-label="Primary navigation" className="mt-6 space-y-1">
          {nav.map(item => <NavigationItem key={item.label} {...item} compact={collapsed} active={active(item.to)} />)}
        </nav>
        <button onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} className="absolute -right-3 top-20 grid h-6 w-6 place-items-center rounded-full border border-slate-200 bg-white text-slate-400 shadow-sm hover:text-cloudera-navy">{collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}</button>
        <div className={`mt-auto border-t border-slate-100 pt-4 ${collapsed ? 'text-center' : 'px-1'}`}>
          {collapsed ? <div className="text-[10px] font-black text-cloudera-navy" title="Tempo Scan Commercial Intelligence">TS</div> : <><div className="text-xs font-extrabold text-cloudera-navy">Tempo Scan</div><div className="mt-0.5 text-[11px] text-slate-500">Commercial Intelligence</div><div className="mt-1.5 text-[10px] text-slate-400">Powered by Cloudera AI</div></>}
        </div>
      </aside>

      <div className={`transition-[padding] duration-200 ${collapsed ? 'lg:pl-20' : 'lg:pl-[232px]'}`}>
        <header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-slate-200 bg-white/95 px-4 shadow-[0_1px_0_rgba(36,19,95,0.02)] backdrop-blur sm:h-[88px] sm:px-8">
          <div className="flex min-w-0 items-center gap-4">
            <button onClick={() => setMobileOpen(true)} aria-label="Open navigation" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-slate-200 text-slate-600 lg:hidden"><Menu size={19} /></button>
            <div className="min-w-0">
              <div className="truncate text-xl font-black leading-tight tracking-[-0.02em] text-cloudera-navy sm:text-[22px]">Commercial Intelligence</div>
              <div className="mt-1 hidden text-xs font-medium leading-none text-slate-400 sm:block sm:text-sm">Tempo Scan</div>
            </div>
          </div>
          <div className="ml-auto mr-4 hidden items-center gap-2.5 border-r border-slate-200 pr-4 sm:mr-5 sm:flex sm:pr-5">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-50 text-slate-400">
              <Clock3 size={16} />
            </span>
            <div className="text-left">
              <div className="text-[9px] font-bold uppercase leading-none tracking-[0.1em] text-slate-400">Latest opened</div>
              <div className="mt-1.5 whitespace-nowrap text-[11px] font-bold leading-none text-cloudera-navy sm:text-xs">{openedAt || '—'}</div>
            </div>
          </div>
          <button className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white p-2 pr-3.5 shadow-sm transition hover:bg-slate-50" aria-label="User profile">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-cloudera-navy text-xs font-extrabold text-white">AD</span>
            <span className="hidden text-left sm:block"><span className="block text-[13px] font-extrabold leading-tight text-cloudera-navy">Andi Dharma</span><span className="mt-1 block text-[10px] leading-none text-slate-400">Management</span></span>
          </button>
        </header>
        <main className="min-w-0 p-4 sm:p-5 xl:p-6 2xl:p-7">{children}</main>
      </div>

      {mobileOpen && <div className="fixed inset-0 z-50 bg-cloudera-navy/20" onMouseDown={event => { if (event.target === event.currentTarget) setMobileOpen(false) }}><aside role="dialog" aria-modal="true" aria-label="Main navigation" className="flex h-full w-[min(84vw,300px)] flex-col bg-white p-4 shadow-2xl"><div className="flex items-center justify-between"><BrandMark /><button onClick={() => setMobileOpen(false)} aria-label="Close navigation" className="grid h-9 w-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"><X size={18} /></button></div><div className="mt-3 text-xs font-bold text-cloudera-navy">Commercial Intelligence</div><nav className="mt-7 space-y-1">{nav.map(item => <NavigationItem key={item.label} {...item} compact={false} active={active(item.to)} onNavigate={() => setMobileOpen(false)} />)}</nav><div className="mt-auto border-t border-slate-100 pt-4"><div className="text-xs font-extrabold text-cloudera-navy">Tempo Scan</div><div className="mt-0.5 text-[11px] text-slate-500">Commercial Intelligence</div><div className="mt-1.5 text-[10px] text-slate-400">Powered by Cloudera AI</div></div></aside></div>}
    </div>
  )
}

function NavigationItem({ to, label, icon: Icon, compact, active, onNavigate }: { to: string | null; label: string; icon: typeof LayoutDashboard; compact: boolean; active: boolean; onNavigate?: () => void }) {
  const classes = `flex h-11 items-center rounded-xl text-xs font-bold transition ${compact ? 'justify-center px-1' : 'gap-2.5 px-2'} ${active ? 'bg-orange-50 text-cloudera-orange ring-1 ring-inset ring-orange-100' : to ? 'text-slate-600 hover:bg-slate-50 hover:text-cloudera-navy' : 'cursor-default text-slate-400'}`
  const content = <><span aria-hidden="true" className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg transition ${active ? 'bg-white text-cloudera-orange shadow-sm' : 'text-slate-500'}`}><Icon size={17} strokeWidth={2.1} /></span><span className={compact ? 'sr-only' : ''}>{label}</span>{!to && !compact && <span className="ml-auto text-[8px] font-bold uppercase tracking-wide text-slate-300">Soon</span>}</>
  if (!to) return <div className={classes} aria-disabled="true" title={compact ? label : undefined}>{content}</div>
  return <Link href={to} onClick={onNavigate} className={classes} title={compact ? label : undefined}>{content}</Link>
}

function CompactBrand() { return <div className="grid h-9 w-9 place-items-center rounded-lg bg-cloudera-orange text-sm font-black text-white" aria-label="Cloudera">C</div> }

function formatOpenedAt(value: Date) {
  const parts = new Intl.DateTimeFormat('en-US', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    hour12: false, timeZone: 'Asia/Jakarta',
  }).formatToParts(value)
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value || ''
  return `${part('day')} ${part('month')} ${part('year')}, ${part('hour')}:${part('minute')} WIB`
}
