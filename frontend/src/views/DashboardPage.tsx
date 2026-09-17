'use client'

import { FormEvent, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  ArrowRight, ArrowUp, Bot, CalendarDays, CheckCircle2, ChevronDown, CircleDollarSign, LineChart as LineChartIcon,
  CloudSun, MapPin, MessageSquareText, Package, RefreshCcw, RotateCcw, Store,
  Target, TrendingUp, Undo2, X,
} from 'lucide-react'
import {
  CartesianGrid, Cell, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useRouter } from 'next/navigation'
import { AiAppliedContext } from '../components/AiAppliedContext'
import { ChartCard } from '../components/ChartCard'
import { KpiCard } from '../components/KpiCard'
import { PageIntro } from '../components/PageIntro'
import { api } from '../lib/api'
import { useDashboardState } from '../lib/dashboardState'
import { actionLabel, dashboardSectionForAction, partitionDashboardAiActions, selectDashboardActions } from '../lib/dashboardAiActions'
import { formatFloatingAnswerText, formatFloatingDriver } from '../lib/floatingAnswerFormatting'
import { useFetch } from '../hooks/useFetch'
import type { AppliedContextItem, ChatResponse, DashboardOverview, UIAction } from '../types/api'

const pieColors = ['#FF5A1F', '#24135F', '#635BFF', '#9A8CFF', '#CBD5E1']
const suggestedQuestions = [
  'Kenapa sales turun bulan ini?',
  'Region mana yang turun paling besar?',
  'Channel mana yang paling terdampak?',
  'Produk mana yang menjadi driver utama?',
  'Bagaimana forecast bulan depan?',
]

type FilterOptions = { region: string[]; product: string[]; channel: string[] }
type DrawerMessage = { role: 'user' | 'assistant'; content: string; response?: ChatResponse; automaticActions?: ChatResponse['ui_actions']; pendingActions?: ChatResponse['ui_actions'] }

export function DashboardPage() {
  const { state, previousDashboardState, applyActions, applyDashboardAiActions, undoAiChanges, setFilter, removeAppliedContext, reset } = useDashboardState()
  const { data, loading, error } = useFetch(() => api.dashboard(state), [state.revision])
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [focusedSection, setFocusedSection] = useState<string | null>(null)
  const focusTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cachedOptions = useRef<FilterOptions>({ region: [], product: [], channel: [] })

  useEffect(() => () => { if (focusTimer.current) clearTimeout(focusTimer.current) }, [])

  function focusSection(sectionId: string) {
    focusDashboardSection(sectionId)
    setFocusedSection(sectionId)
    if (focusTimer.current) clearTimeout(focusTimer.current)
    focusTimer.current = setTimeout(() => setFocusedSection(null), 2000)
  }

  if (data) {
    cachedOptions.current = {
      region: mergeOptions(cachedOptions.current.region, data.region_sales.map(row => row.region)),
      product: mergeOptions(cachedOptions.current.product, data.top_products.map(row => row.product)),
      channel: mergeOptions(cachedOptions.current.channel, data.channel_share.map(row => row.channel)),
    }
  }
  if (loading && !data) return <PageLoading label="Loading governed business view..." />
  if (error || !data) return <PageError message={error || 'Dashboard unavailable'} />

  const netSales = data.kpis.find(item => item.key === 'net_sales')
  const growth = data.kpis.find(item => item.key === 'growth')
  const topRegion = data.kpis.find(item => item.key === 'top_region')
  const latestPeriod = periodLabel(data, state.date_range.preset)
  const forecast = data.forecast
  const opportunity = data.market_signals?.opportunity_score
  const trend = forecastTrend(data)

  return (
    <div className="min-w-0">
      <PageIntro
        title="Commercial Dashboard"
        subtitle="Sales performance and commercial insights from governed business data."
        action={data.refreshed_at ? <div className="flex items-center gap-1.5 text-xs text-slate-400"><RefreshCcw size={16} strokeWidth={2} />Last refreshed: {formatRefresh(data.refreshed_at)}</div> : undefined}
      />

      <DashboardFilters
        dateLabel={latestPeriod}
        options={cachedOptions.current}
        datePreset={state.date_range.preset || 'current_month'}
        filters={state.filters}
        onDateChange={value => applyActions([{ type: 'SET_DATE_RANGE', value }])}
        onFilterChange={(target, value) => setFilter(target, value ? [value] : [])}
        onReset={reset}
      />
      <AiAppliedContext items={displayContextItems(state.ai_applied_context, latestPeriod)} onRemove={removeAppliedContext} onReset={reset} onUndo={undoAiChanges} canUndo={Boolean(previousDashboardState)} />

      <section id="executive-kpis" aria-label="Executive KPIs" className="mt-4 scroll-mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <KpiCard label="Net Sales" value={netSales?.value} format={netSales?.format || 'text'} delta={netSales?.delta} icon={CircleDollarSign} context="Selected period" highlighted={isHighlighted(state.highlights, 'net_sales')} />
        <KpiCard label="Growth vs Previous Period" value={growth?.value} format={growth?.format || 'percent'} delta={growth?.delta} icon={TrendingUp} context="Compared with prior period" highlighted={isHighlighted(state.highlights, 'growth')} />
        <KpiCard label="Forecast Next Period" value={forecast?.value} format={forecast?.format || 'currency_billion'} delta={forecast?.delta} icon={LineChartIcon} context={forecast?.period || 'No governed forecast in this response'} highlighted={isHighlighted(state.highlights, 'forecast')} />
        <KpiCard label="Top Region" value={topRegion?.value} format={topRegion?.format || 'text'} delta={topRegion?.delta} icon={MapPin} context={latestPeriod} highlighted={isHighlighted(state.highlights, 'top_region')} />
        <KpiCard label="Market Opportunity" value={opportunity} format="score" delta={null} icon={Target} context={data.market_signals?.opportunity_context || 'No governed market signal in this response'} highlighted={isHighlighted(state.highlights, 'market_opportunity')} />
      </section>

      <div className="mt-4 min-w-0">
        <div id="sales-performance" data-focused={focusedSection === 'sales-performance'} className={focusClass('min-w-0 scroll-mt-4 [&>section]:h-full', focusedSection === 'sales-performance')}>
          <ChartCard title="Sales Performance" subtitle={`Historical actual sales${forecast ? ' with next-period forecast' : ''} • Million IDR`} action={<ChartKey hasForecast={Boolean(forecast)} />}>
            {trend.length ? (
              <div className="h-[280px] sm:h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend} margin={{ top: 10, right: 12, left: 2, bottom: 0 }}>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis dataKey="month" tickFormatter={formatAxisMonth} tick={{ fontSize: 11, fill: '#7C849A' }} axisLine={false} tickLine={false} />
                    <YAxis width={58} tickFormatter={formatAxisSales} tick={{ fontSize: 11, fill: '#7C849A' }} axisLine={false} tickLine={false} />
                    <Tooltip formatter={value => [formatSales(Number(value)), 'Sales']} labelFormatter={formatAxisMonth} />
                    <Line type="monotone" dataKey="actual" name="Actual" stroke="#FF5A1F" strokeWidth={2.5} dot={{ r: 3, fill: '#FF5A1F', strokeWidth: 0 }} connectNulls={false} />
                    {forecast && <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#635BFF" strokeWidth={2.5} strokeDasharray="6 5" dot={{ r: 3, fill: '#635BFF', strokeWidth: 0 }} connectNulls />}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : <EmptyState message="Sales trend is not available for this context." />}
          </ChartCard>
        </div>
      </div>

      <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-12">
        <div id="sales-by-region" data-focused={focusedSection === 'sales-by-region'} className={focusClass('min-w-0 scroll-mt-4 xl:col-span-5 [&>section]:h-full', focusedSection === 'sales-by-region')}><ChartCard title="Sales by Region" subtitle={`${latestPeriod} • Million IDR`}>{data.region_sales.length ? <RegionRanking rows={data.region_sales} /> : <EmptyState message="No regional sales are available for these filters." />}</ChartCard></div>
        <div id="product-performance" data-focused={focusedSection === 'product-performance'} className={focusClass('min-w-0 scroll-mt-4 xl:col-span-7 [&>section]:h-full', focusedSection === 'product-performance')}><ChartCard title="Product Performance" subtitle="Top products in the selected commercial context">{data.top_products.length ? <ProductTable rows={data.top_products} /> : <EmptyState message="No product sales are available for these filters." />}</ChartCard></div>
      </div>

      <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-12">
        <div id="channel-contribution" data-focused={focusedSection === 'channel-contribution'} className={focusClass('min-w-0 scroll-mt-4 xl:col-span-5 [&>section]:h-full', focusedSection === 'channel-contribution')}><ChartCard title="Channel Contribution" subtitle="Share of selected-period sales">{data.channel_share.length ? <ChannelDistribution rows={data.channel_share} /> : <EmptyState message="No channel contribution is available for these filters." />}</ChartCard></div>
        <div id="market-signals" data-focused={focusedSection === 'market-signals'} className={focusClass('min-w-0 scroll-mt-4 xl:col-span-7 [&>section]:h-full', focusedSection === 'market-signals')}><ChartCard title="Market Opportunity & External Signals" subtitle="Governed signals available for the active context"><ExternalSignals signals={data.market_signals} hasProductContext={Boolean(state.filters.product?.[0])} /></ChartCard></div>
      </div>

      <button onClick={() => setAssistantOpen(true)} className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-cloudera-navy px-4 py-3 text-sm font-bold text-white shadow-xl transition hover:-translate-y-0.5 hover:bg-[#24135f] sm:bottom-7 sm:right-7" aria-label="Ask AI"><MessageSquareText size={16} strokeWidth={2} className="text-cloudera-orange" />Ask AI</button>
      {assistantOpen && <DashboardAssistant contextItems={contextItems(latestPeriod, state.filters)} appliedItems={displayContextItems(state.ai_applied_context, latestPeriod)} periodLabel={latestPeriod} state={state} applyActions={applyActions} applyDashboardAiActions={applyDashboardAiActions} canUndo={Boolean(previousDashboardState)} onFocusSection={focusSection} onUndo={undoAiChanges} onReset={reset} onClose={() => setAssistantOpen(false)} />}
    </div>
  )
}

function DashboardFilters({ dateLabel, datePreset, filters, options, onDateChange, onFilterChange, onReset }: {
  dateLabel: string
  datePreset: string
  filters: Record<string, string[]>
  options: FilterOptions
  onDateChange: (value: string) => void
  onFilterChange: (target: string, value: string) => void
  onReset: () => void
}) {
  return (
    <section aria-label="Dashboard filters" className="card grid gap-3 p-3 sm:grid-cols-2 lg:grid-cols-[1.15fr_1fr_1fr_1fr_auto] lg:items-end">
      <FilterSelect label="Date Range" icon={CalendarDays} value={datePreset} onChange={onDateChange} options={[{ value: 'current_month', label: dateLabel }, { value: 'previous_month', label: 'Previous period' }, { value: 'last_3_months', label: 'Last 3 months' }]} />
      <FilterSelect label="Region" icon={MapPin} value={filters.region?.[0] || ''} onChange={value => onFilterChange('region', value)} options={[{ value: '', label: 'All Regions' }, ...options.region.map(value => ({ value, label: value }))]} />
      <FilterSelect label="Product" icon={Package} value={filters.product?.[0] || ''} onChange={value => onFilterChange('product', value)} options={[{ value: '', label: 'All Products' }, ...options.product.map(value => ({ value, label: value }))]} />
      <FilterSelect label="Channel" icon={Store} value={filters.channel?.[0] || ''} onChange={value => onFilterChange('channel', value)} options={[{ value: '', label: 'All Channels' }, ...options.channel.map(value => ({ value, label: value }))]} />
      <button type="button" onClick={onReset} className="btn-secondary h-[42px] px-3" aria-label="Reset dashboard filters"><RotateCcw size={16} strokeWidth={2} /><span className="lg:hidden 2xl:inline">Reset</span></button>
    </section>
  )
}

function FilterSelect({ label, value, options, onChange, icon: Icon }: { label: string; value: string; options: { value: string; label: string }[]; onChange: (value: string) => void; icon: typeof CalendarDays }) {
  return <label className="min-w-0"><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-[.12em] text-slate-400">{label}</span><span className="relative flex items-center"><Icon size={16} strokeWidth={2} className="pointer-events-none absolute left-3 z-10 text-slate-400" /><select aria-label={label} value={value} onChange={event => onChange(event.target.value)} className="h-[42px] w-full appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-8 text-xs font-semibold text-cloudera-navy outline-none transition hover:border-slate-300 focus:border-cloudera-violet focus:ring-2 focus:ring-violet-100">{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select><ChevronDown size={16} strokeWidth={2} className="pointer-events-none absolute right-3 text-slate-400" /></span></label>
}

function DashboardAssistant({ contextItems, appliedItems, periodLabel, state, applyActions, applyDashboardAiActions, canUndo, onFocusSection, onUndo, onReset, onClose }: { contextItems: string[]; appliedItems: AppliedContextItem[]; periodLabel: string; state: Parameters<typeof api.dashboard>[0]; applyActions: (actions: ChatResponse['ui_actions']) => void; applyDashboardAiActions: (actions: ChatResponse['ui_actions']) => void; canUndo: boolean; onFocusSection: (sectionId: string) => void; onUndo: () => void; onReset: () => void; onClose: () => void }) {
  const router = useRouter()
  const [messages, setMessages] = useState<DrawerMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(question = input) {
    const value = question.trim()
    if (!value || loading) return
    const history = messages.map(message => ({ role: message.role, content: message.content }))
    setMessages(current => [...current, { role: 'user', content: value }])
    setInput('')
    setLoading(true)
    try {
      const response = await api.chat(value, history, state)
      const actions = partitionDashboardAiActions(response.ui_actions)
      if (actions.automatic.length) applyDashboardAiActions(actions.automatic)
      setMessages(current => [...current, { role: 'assistant', content: response.answer.summary, response, automaticActions: actions.automatic, pendingActions: selectDashboardActions(actions.confirmationRequired) }])
    } catch {
      setMessages(current => [...current, { role: 'assistant', content: 'Unable to complete the analysis right now. Please try again.' }])
    } finally { setLoading(false) }
  }

  function confirmAction(messageIndex: number, actionIndex: number) {
    const message = messages[messageIndex]
    const action = message?.pendingActions?.[actionIndex]
    if (!action) return
    applyActions([action])
    setMessages(current => current.map((item, index) => index === messageIndex ? { ...item, pendingActions: item.pendingActions?.filter((_, pendingIndex) => pendingIndex !== actionIndex) } : item))
    onFocusSection(dashboardSectionForAction(action))
  }

  const latestQuestion = [...messages].reverse().find(message => message.role === 'user')?.content || input.trim()
  function continueInAskAi() {
    const latestResponse = [...messages].reverse().find(message => message.response)?.response
    const params = new URLSearchParams()
    if (latestQuestion) params.set('q', latestQuestion)
    if (latestResponse) {
      params.set('summary', latestResponse.answer.summary)
      params.set('intent', latestResponse.metadata.intent)
    }
    params.set('period', state.date_range.preset || [state.date_range.start, state.date_range.end].filter(Boolean).join(':'))
    for (const target of ['region', 'product', 'channel']) if (state.filters[target]?.[0]) params.set(target, state.filters[target][0])
    router.push(`/ask-ai?${params.toString()}`)
  }

  return (
    <div className="fixed inset-0 z-50 bg-cloudera-navy/15 sm:backdrop-blur-[1px]" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
      <aside role="dialog" aria-modal="true" aria-label="SCAN" className="ml-auto flex h-full w-full flex-col bg-white shadow-2xl sm:max-w-[410px]">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3.5"><div className="flex items-center gap-2.5"><span className="grid h-8 w-8 place-items-center rounded-lg bg-violet-50 text-cloudera-violet"><Bot size={16} strokeWidth={2} /></span><div><div className="text-sm font-extrabold text-cloudera-navy">SCAN</div><div className="text-[10px] text-emerald-600">● Governed data connected</div></div></div><button onClick={onClose} aria-label="Close AI assistant" className="grid h-9 w-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"><X size={16} strokeWidth={2} /></button></header>
        <div className="border-b border-slate-100 bg-slate-50 px-4 py-3"><div className="text-[10px] font-bold uppercase tracking-[.12em] text-slate-400">Current dashboard context</div><div className="mt-2 flex flex-wrap gap-1.5">{contextItems.map(item => <span key={item} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">{item}</span>)}</div>{appliedItems.length > 0 && <div className="mt-2.5 flex items-center gap-3 border-t border-slate-200 pt-2"><span className="mr-auto text-[10px] font-extrabold uppercase tracking-[.1em] text-cloudera-orange">Applied by AI</span>{canUndo && <button type="button" onClick={onUndo} className="inline-flex items-center gap-1 text-[11px] font-bold text-cloudera-violet"><Undo2 size={12} />Undo AI changes</button>}<button type="button" onClick={onReset} className="text-[11px] font-bold text-slate-500">Reset all</button></div>}</div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && <><div className="rounded-xl border border-violet-100 bg-violet-50/60 p-3 text-xs leading-5 text-slate-600">Ask a commercial question. Answers use the same controlled API and shared dashboard context as Ask AI.</div><div className="space-y-2">{suggestedQuestions.map(question => <button key={question} onClick={() => submit(question)} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-left text-xs font-semibold text-slate-600 transition hover:border-orange-200 hover:text-cloudera-navy">{question}</button>)}</div></>}
          {messages.map((message, index) => message.role === 'user'
            ? <div key={`${message.role}-${index}`} className="ml-auto max-w-[88%] rounded-xl bg-cloudera-navy px-3 py-2.5 text-xs leading-5 text-white">{message.content}</div>
            : <DrawerAnswer key={`${message.role}-${index}`} message={message} periodLabel={periodLabel} onConfirm={actionIndex => confirmAction(index, actionIndex)} onContinue={continueInAskAi} />)}
          {loading && <div className="flex items-center gap-2 text-xs text-slate-500"><span className="h-2 w-2 animate-pulse rounded-full bg-cloudera-orange" />Analyzing governed data…</div>}
        </div>
        <form onSubmit={(event: FormEvent) => { event.preventDefault(); submit() }} className="sticky bottom-0 border-t border-slate-200 bg-white p-3"><div className="flex items-end gap-2 rounded-xl border border-slate-200 p-2 focus-within:border-cloudera-violet"><textarea value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key !== 'Enter' || event.shiftKey || !input.trim() || loading) return; event.preventDefault(); submit() }} rows={2} placeholder="Ask about this dashboard..." className="min-h-[44px] flex-1 resize-none bg-transparent px-1 py-1 text-sm outline-none" /><button disabled={loading || !input.trim()} aria-label="Send question" className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-cloudera-orange text-white disabled:opacity-40"><ArrowUp size={16} strokeWidth={2} /></button></div></form>
      </aside>
    </div>
  )
}

function DrawerAnswer({ message, periodLabel, onConfirm, onContinue }: { message: DrawerMessage; periodLabel: string; onConfirm: (index: number) => void; onContinue: () => void }) {
  const drivers = message.response?.answer.drivers.slice(0, 3).map(formatFloatingDriver).filter(Boolean) || []
  return <div aria-label={message.response ? 'AI response' : 'Assistant message'} className="max-w-[94%] rounded-xl border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-700 shadow-sm">
    {message.response && <div className="text-[10px] font-extrabold uppercase tracking-[.1em] text-slate-400">Summary</div>}
    <p className={`${message.response ? 'mt-1.5 ' : ''}font-semibold text-cloudera-navy`}>{formatFloatingAnswerText(message.content)}</p>
    {drivers.length > 0 && <div className="mt-3"><div className="text-[10px] font-extrabold uppercase tracking-[.1em] text-slate-400">Key drivers</div><ul className="mt-1.5 space-y-1">{drivers.map(driver => <li key={driver} className="flex gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cloudera-orange" />{driver}</li>)}</ul></div>}
    {Boolean(message.automaticActions?.length) && <div className="mt-3 rounded-lg border border-emerald-100 bg-emerald-50 p-2.5"><div className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-[.1em] text-emerald-700"><CheckCircle2 size={13} />Applied to dashboard</div><div className="mt-1 font-semibold text-emerald-800">{automaticActionLabels(message.automaticActions || [], periodLabel).join(' • ')}</div></div>}
    {Boolean(message.pendingActions?.length) && <div className="mt-3 space-y-2"><div className="text-[10px] font-extrabold uppercase tracking-[.1em] text-slate-400">Next actions</div>{message.pendingActions?.map((action, index) => <button key={`${action.type}-${index}`} type="button" onClick={() => onConfirm(index)} className="w-full rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-left font-bold text-cloudera-violet hover:bg-violet-100">{actionLabel(action)}</button>)}</div>}
    {message.response && <button type="button" onClick={onContinue} className="mt-3 inline-flex items-center gap-1.5 font-bold text-cloudera-violet hover:text-cloudera-navy">Continue analysis in Ask AI <ArrowRight size={13} /></button>}
  </div>
}

function RegionRanking({ rows }: { rows: DashboardOverview['region_sales'] }) {
  const max = Math.max(...rows.map(row => Number(row.sales)), 1)
  return <div className="min-h-[250px] space-y-3 pt-1">{rows.map((row, index) => <div key={row.region}><div className="mb-1.5 flex items-center justify-between gap-3 text-xs"><span className="truncate font-semibold text-slate-600"><span className="mr-2 text-slate-300">{index + 1}</span>{row.region}</span><span className="shrink-0 font-bold tabular-nums text-cloudera-navy">{formatSales(Number(row.sales))}</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-cloudera-orange" style={{ width: `${Math.max(4, Number(row.sales) / max * 100)}%`, opacity: 1 - index * .08 }} /></div></div>)}</div>
}

function ProductTable({ rows }: { rows: DashboardOverview['top_products'] }) {
  return <div className="min-h-[250px] overflow-x-auto"><table className="w-full min-w-[440px] text-left text-xs"><thead className="border-b border-slate-200 text-[10px] uppercase tracking-[.1em] text-slate-400"><tr><th className="pb-2.5 font-bold">Rank</th><th className="pb-2.5 font-bold">Product</th><th className="pb-2.5 font-bold">Category</th><th className="pb-2.5 text-right font-bold">Sales</th></tr></thead><tbody>{rows.slice(0, 6).map((row, index) => <tr key={row.product} className="border-b border-slate-100 last:border-0"><td className="py-3 font-bold text-slate-300">{String(index + 1).padStart(2, '0')}</td><td className="py-3 font-bold text-cloudera-navy">{row.product}</td><td className="py-3 text-slate-500">{row.category}</td><td className="py-3 text-right font-bold tabular-nums text-slate-700">{formatSales(Number(row.sales))}</td></tr>)}</tbody></table></div>
}

function ChannelDistribution({ rows }: { rows: DashboardOverview['channel_share'] }) {
  return <div className="grid min-h-[250px] items-center gap-2 sm:grid-cols-[160px_1fr]"><div className="h-[160px]"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={rows} dataKey="share" nameKey="channel" innerRadius={44} outerRadius={64} paddingAngle={2} stroke="none">{rows.map((row, index) => <Cell key={row.channel} fill={pieColors[index % pieColors.length]} />)}</Pie><Tooltip formatter={value => [`${Number(value).toFixed(1)}%`, 'Share']} /></PieChart></ResponsiveContainer></div><div className="space-y-2.5">{rows.map((row, index) => <div key={row.channel} className="flex items-center justify-between gap-3 text-xs"><span className="flex min-w-0 items-center gap-2 text-slate-600"><span className="h-2 w-2 shrink-0 rounded-full" style={{ background: pieColors[index % pieColors.length] }} /><span className="truncate">{row.channel}</span></span><span className="font-bold tabular-nums text-cloudera-navy">{Number(row.share).toFixed(1)}%</span></div>)}</div></div>
}

function ExternalSignals({ signals, hasProductContext }: { signals?: DashboardOverview['market_signals']; hasProductContext: boolean }) {
  const rows = businessSignalRows(signals)
  if (!rows.length) {
    if (!hasProductContext) {
      return (
        <EmptyState
          icon={<CloudSun size={20} strokeWidth={1.75} />}
          message="Select a product or category to view external market signals."
          hint="Use the Product filter or Ask AI to explore market intelligence."
        />
      )
    }
    return <EmptyState icon={<CloudSun size={20} strokeWidth={1.75} />} message="No external business signals are available for the selected context." />
  }
  return <div className="grid min-h-[250px] content-start gap-x-8 sm:grid-cols-2">{rows.map(row => <div key={row.label} className="flex items-center justify-between border-b border-slate-100 py-3.5 text-xs"><span className="text-slate-500">{row.label}</span><span className="font-extrabold tabular-nums text-cloudera-navy">{row.display}</span></div>)}</div>
}

function businessSignalRows(signals?: DashboardOverview['market_signals']) {
  const candidates = [
    { label: 'Market Growth', value: signals?.market_growth, display: (value: number) => `${value > 0 ? '+' : ''}${value.toFixed(1)}%` },
    { label: 'Competitive Pressure', value: signals?.competitive_pressure, display: (value: number) => value.toFixed(1) },
    { label: 'Distribution Gap', value: signals?.distribution_gap, display: (value: number) => `${value.toFixed(1)}%` },
    { label: 'Weather Correlation', value: signals?.weather_correlation, display: (value: number) => value.toFixed(2) },
    { label: 'Opportunity Score', value: signals?.opportunity_score, display: (value: number) => value.toFixed(1) },
  ]
  return candidates
    .filter((row): row is typeof row & { value: number } => typeof row.value === 'number' && Number.isFinite(row.value))
    .map(row => ({ label: row.label, display: row.display(row.value) }))
}

function ChartKey({ hasForecast }: { hasForecast: boolean }) { return <div className="hidden items-center gap-3 text-[10px] font-semibold text-slate-500 sm:flex"><span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-cloudera-orange" />Actual</span>{hasForecast && <span className="flex items-center gap-1.5"><span className="w-4 border-t-2 border-dashed border-cloudera-violet" />Forecast</span>}</div> }
function EmptyState({ message, icon, hint }: { message: string; icon?: ReactNode; hint?: string }) { return <div className="flex min-h-[120px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-5 text-center text-xs leading-5 text-slate-500">{icon && <span className="mb-2 text-slate-400">{icon}</span>}{message}{hint && <span className="mt-1 text-[11px] text-slate-400">{hint}</span>}</div> }
function PageLoading({ label }: { label: string }) { return <div className="card-pad flex min-h-[280px] items-center justify-center"><div className="text-center"><div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-cloudera-orange" /><div className="mt-3 text-sm font-semibold text-slate-500">{label}</div></div></div> }
function PageError({ message }: { message: string }) { return <div className="card-pad border-rose-200 bg-rose-50 text-sm text-rose-700">Dashboard unavailable: {message}.</div> }

function mergeOptions(current: string[], incoming: string[]) { return [...new Set([...current, ...incoming].filter(Boolean))] }
function isHighlighted(highlights: { target: string }[], key: string) { return highlights.some(item => item.target === key || (item.target === 'region' && key === 'top_region')) }
function formatSales(value: number) { return value >= 1_000_000 ? `Rp ${(value / 1_000_000).toFixed(2)}T` : value >= 1_000 ? `Rp ${(value / 1_000).toFixed(1)}B` : `Rp ${value.toFixed(0)}M` }
function formatAxisSales(value: number) { return value >= 1_000 ? `${(value / 1_000).toFixed(0)}B` : `${value.toFixed(0)}M` }
function formatAxisMonth(value: unknown) { const text = String(value); const parsed = new Date(`${text.length === 7 ? `${text}-01` : text}T00:00:00Z`); return Number.isNaN(parsed.getTime()) ? text : new Intl.DateTimeFormat('en', { month: 'short', year: '2-digit', timeZone: 'UTC' }).format(parsed) }
function formatRefresh(value: string) { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? '' : new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta' }).format(parsed) }
function formatPeriodMonth(value: string) { const parsed = new Date(`${value.length === 7 ? `${value}-01` : value}T00:00:00Z`); return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(parsed) }
function periodLabel(data: DashboardOverview, preset: string | null) { const months = data.sales_trend.map(row => row.month); if (!months.length) return data.period || 'Latest period'; if (preset === 'last_3_months') return `${formatPeriodMonth(months[0])} – ${formatPeriodMonth(months[months.length - 1])}`; if (preset === 'previous_month') return formatPeriodMonth(months[Math.max(0, months.length - 2)]); return formatPeriodMonth(months[months.length - 1]) }
function contextItems(period: string, filters: Record<string, string[]>) { return [period, filters.region?.[0] || 'All Regions', filters.product?.[0] || 'All Products', filters.channel?.[0] || 'All Channels'] }
function displayContextItems(items: AppliedContextItem[], period: string) { return items.map(item => item.kind === 'date_range' ? { ...item, label: period } : item) }
function automaticActionLabels(actions: UIAction[], period: string) { return actions.flatMap(action => action.type === 'SET_FILTER' ? action.value : action.type === 'SET_DATE_RANGE' ? [period] : []) }
function focusClass(base: string, focused: boolean) { return `${base} rounded-2xl transition-all duration-300 ${focused ? 'ring-2 ring-cloudera-orange/50 ring-offset-2' : 'ring-0'}` }
function focusDashboardSection(id: string) { const section = typeof document === 'undefined' ? null : document.getElementById(id); if (section && typeof section.scrollIntoView === 'function') section.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
function forecastTrend(data: DashboardOverview) { const rows = data.sales_trend.map(row => ({ month: row.month, actual: Number(row.sales), forecast: null as number | null })); if (data.forecast && rows.length) { rows[rows.length - 1].forecast = rows[rows.length - 1].actual; rows.push({ month: data.forecast.period, actual: Number.NaN, forecast: Number(data.forecast.value) }) } return rows }
