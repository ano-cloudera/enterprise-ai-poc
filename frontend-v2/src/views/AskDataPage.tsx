'use client'

import { FormEvent, KeyboardEvent, MouseEvent, useEffect, useRef, useState } from 'react'
import { ArrowUp, BarChart3, ChevronDown, Database, Info, Lightbulb, MessageSquareText, PanelLeftClose, PanelLeftOpen, Plus, Square, Table2, Trash2, UserRound } from 'lucide-react'
import { AnswerChart } from '../components/AnswerChart'
import { DataTable } from '../components/DataTable'
import { KpiCard } from '../components/KpiCard'
import { ScanMark } from '../components/ScanMark'
import { api } from '../lib/api'
import { createSessionId, deleteSession, loadSessions, saveSession, sessionTitle, type ChatSession, type StoredMessage } from '../lib/chatSessions'
import { useModelSelection } from '../lib/modelSelection'
import { useChatLayout } from '../layout/AppShell'
import type { ChatResponse, SuggestedQuestion } from '../types/api'

const STARTER_QUESTION_COUNT = 3

export function AskDataPage() {
  const { fullScreenChat, toggleFullScreenChat } = useChatLayout()
  const { selection, select, loading: modelsLoading, error: modelError } = useModelSelection()
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(createSessionId)
  const [messages, setMessages] = useState<StoredMessage[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [starterQuestions, setStarterQuestions] = useState<SuggestedQuestion[]>([])
  const end = useRef<HTMLDivElement>(null)
  const activeRequest = useRef<AbortController | null>(null)

  useEffect(() => setSessions(loadSessions()), [])
  useEffect(() => { if (messages.length) { saveSession({ id: sessionId, title: sessionTitle(messages), updatedAt: Date.now(), messages, selection: selection || undefined }); setSessions(loadSessions()) } }, [messages, selection, sessionId])
  useEffect(() => { end.current?.scrollIntoView?.({ behavior: 'smooth' }) }, [messages, progress])
  useEffect(() => () => activeRequest.current?.abort(), [])
  useEffect(() => { api.randomQueries(STARTER_QUESTION_COUNT).then(response => setStarterQuestions(response.questions)).catch(() => setStarterQuestions([])) }, [])

  async function submit(question = input) {
    const value = question.trim()
    if (!value || loading || !selection) return
    setMessages(current => [...current, { role: 'user', content: value }]); setInput(''); setError(''); setLoading(true)
    const controller = new AbortController()
    activeRequest.current = controller
    let timedOut = false
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort() }, 90_000)
    try {
      for await (const event of api.chatStream(value, sessionId, selection, controller.signal)) {
        if (event.type === 'progress') setProgress(event.label)
        else setMessages(current => [...current, { role: 'assistant', content: event.response.answer.executive_summary, response: event.response }])
      }
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === 'AbortError') {
        setError(timedOut ? 'Request timed out. Please try again.' : 'Request stopped.')
      } else {
        setError('Unable to complete the analysis right now. Please try again.')
      }
    } finally {
      window.clearTimeout(timeout)
      if (activeRequest.current === controller) activeRequest.current = null
      setLoading(false); setProgress(null)
    }
  }

  function stopRequest() { activeRequest.current?.abort() }

  function newChat() { setSessionId(createSessionId()); setMessages([]); setInput(''); setError('') }
  function openSession(session: ChatSession) { setSessionId(session.id); setMessages(session.messages); setInput(''); if (session.selection) select(session.selection) }
  function removeSession(event: MouseEvent, id: string) { event.stopPropagation(); deleteSession(id); setSessions(loadSessions()); if (id === sessionId) newChat() }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) { if (event.key === 'Enter' && !event.shiftKey && input.trim() && !loading) { event.preventDefault(); submit() } }

  return <div className="flex h-[calc(100dvh-136px)] min-w-0 flex-col pb-14 lg:pb-0"><div className={`grid min-h-0 flex-1 transition-[grid-template-columns,gap] duration-300 ease-in-out ${fullScreenChat ? 'gap-0 xl:grid-cols-[0_minmax(0,1fr)]' : 'gap-4 xl:grid-cols-[214px_minmax(0,1fr)]'}`}>
    <aside aria-label="Conversation history sidebar" aria-hidden={fullScreenChat} inert={fullScreenChat} className={`card hidden overflow-hidden transition-[opacity,transform,padding,border-width] duration-300 ease-in-out xl:block ${fullScreenChat ? 'pointer-events-none -translate-x-3 border-0 p-0 opacity-0' : 'translate-x-0 overflow-y-auto p-4 opacity-100'}`}><button className="btn-primary w-full" onClick={newChat}><Plus size={16} />New Chat</button><div className="mt-6 text-sm font-extrabold text-cloudera-navy">Recent conversations</div>{sessions.length ? <div className="mt-3 space-y-2">{sessions.map(session => <div key={session.id} className="group relative rounded-xl border border-transparent hover:bg-slate-50"><button className="w-full p-3 pr-9 text-left text-xs" onClick={() => openSession(session)}><MessageSquareText size={14} className="mr-2 inline" />{session.title}</button><button aria-label="Delete conversation" className="absolute right-2 top-2 text-slate-400" onClick={event => removeSession(event, session.id)}><Trash2 size={13} /></button></div>)}</div> : <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs text-slate-500">No conversations yet.</div>}</aside>
    <section className="card flex min-h-0 min-w-0 flex-col overflow-hidden transition-[width] duration-300 ease-in-out"><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div className="flex items-center gap-2"><button type="button" aria-label={fullScreenChat ? 'Exit full screen chat' : 'Enter full screen chat'} aria-pressed={fullScreenChat} onClick={toggleFullScreenChat} className="hidden h-9 w-9 shrink-0 place-items-center rounded-xl border border-slate-200 text-slate-500 transition-colors hover:bg-slate-50 hover:text-cloudera-navy lg:grid">{fullScreenChat ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}</button><div className="text-sm font-extrabold text-cloudera-navy">Scan Intelligence</div></div><div className="chip"><Database size={13} />Ossie · Impala</div></div>
      <div role="log" aria-label="Conversation" className={`min-h-0 flex-1 overflow-y-auto p-5 ${messages.length ? 'space-y-5' : 'flex'}`}>
        {!messages.length && <div className="m-auto max-w-2xl text-center"><ScanMark size={56} className="mx-auto" rounded="2xl" /><h1 className="mt-5 text-2xl font-black text-cloudera-navy">Ask your TEMPO commercial data</h1><p className="mt-2 text-sm leading-6 text-slate-500">Get a grounded answer, governed data, and a relevant visualization without Agent Studio orchestration.</p>{starterQuestions.length > 0 && <div className="mt-6 grid gap-2 text-left sm:grid-cols-3">{starterQuestions.map(item => <button key={item.id} type="button" onClick={() => submit(item.question)} disabled={!selection || loading} className="rounded-xl border border-slate-200 bg-white p-3 text-left text-sm leading-5 text-slate-600 transition-colors hover:border-cloudera-orange/40 hover:bg-orange-50/40 disabled:opacity-50">{item.question}</button>)}</div>}</div>}
        {messages.map((message, index) => message.role === 'user' ? <div key={index} className="ml-auto flex max-w-[80%] justify-end gap-2"><div className="rounded-2xl rounded-tr-md bg-cloudera-navy px-4 py-3 text-sm leading-6 text-white">{message.content}</div><UserRound size={28} className="rounded-full bg-slate-200 p-1.5" /></div> : <div key={index} className="flex gap-3"><ScanMark size={36} /><div className="min-w-0 max-w-[1000px] flex-1 rounded-2xl border border-slate-200 bg-white p-6">{message.response ? <StructuredAnswer response={message.response} /> : message.content}</div></div>)}
        {loading && <div className="flex items-center gap-3"><ScanMark size={36} className="animate-pulse" /><div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500"><span className="flex gap-1"><span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cloudera-orange [animation-delay:-0.3s]" /><span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cloudera-orange [animation-delay:-0.15s]" /><span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cloudera-orange" /></span><span className="font-medium text-slate-600">{progress || 'AI is analyzing...'}</span></div></div>}
        {error && <div className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}<div ref={end} />
      </div>
      <form onSubmit={(event: FormEvent) => { event.preventDefault(); submit() }} className="border-t border-slate-200 p-4"><div className="flex items-end gap-2 rounded-2xl border border-slate-200 p-2"><textarea rows={2} value={input} onChange={event => setInput(event.target.value)} onKeyDown={keyDown} placeholder="Ask a commercial question..." className="min-h-[48px] flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none" />{loading ? <button type="button" aria-label="Stop request" onClick={stopRequest} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cloudera-orange text-white transition-colors hover:bg-rose-600"><Square size={14} fill="currentColor" /></button> : <button type="submit" aria-label="Send question" disabled={!selection || !input.trim()} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cloudera-orange text-white disabled:opacity-40"><ArrowUp size={18} /></button>}</div>{(modelsLoading || modelError || !selection) && <div className="mt-2 text-xs text-amber-700">{modelsLoading ? 'Discovering configured models…' : modelError || 'No configured model is available. Open Settings or contact the operator.'}</div>}</form>
    </section>
  </div></div>
}

function StructuredAnswer({ response }: { response: ChatResponse }) {
  const kpiField = response.chart_spec?.type === 'kpi' ? response.chart_spec.y || response.data.columns[0] : null
  const kpiValue = kpiField ? response.data.rows[0]?.[kpiField] : undefined
  const visualChartTypes = ['bar', 'line', 'area', 'scatter', 'pie']
  const hasVisualChart = Boolean(
    response.chart_spec && visualChartTypes.includes(response.chart_spec.type) && response.chart_spec.x && response.chart_spec.y && response.data.rows.length > 0
  )
  const [showTable, setShowTable] = useState(!hasVisualChart)
  const titles: Record<ChatResponse['status'], string> = {
    SUCCESS: response.strategy === 'conversational' ? 'Welcome' : 'Direct answer',
    CLARIFICATION: 'A quick clarification',
    NO_DATA: 'No matching data',
    UNSUPPORTED: 'Outside the current scope',
    ERROR: 'Something went wrong',
  }
  const statusStyles: Record<ChatResponse['status'], string> = {
    SUCCESS: 'bg-emerald-50 text-emerald-700',
    CLARIFICATION: 'bg-amber-50 text-amber-700',
    NO_DATA: 'bg-slate-100 text-slate-600',
    UNSUPPORTED: 'bg-slate-100 text-slate-600',
    ERROR: 'bg-rose-50 text-rose-700',
  }

  const dataReferenceParts = response.answer.data_reference ? splitDataReference(response.answer.data_reference) : null

  return <div aria-label="AI response" className="space-y-5 text-sm leading-7">
    <div>
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-extrabold uppercase tracking-wide text-cloudera-navy">{titles[response.status]}</div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${statusStyles[response.status]}`}>{response.status}</span>
      </div>
      <p className="mt-3 text-base font-semibold leading-7 text-slate-900">{response.answer.direct_answer}</p>
      {response.answer.executive_summary !== response.answer.direct_answer && <p className="mt-2 text-slate-600">{response.answer.executive_summary}</p>}
    </div>

    {response.answer.insights.length > 0 && <section className="rounded-xl border border-slate-100 bg-slate-50/70 p-4">
      <div className="flex items-center gap-2 text-xs font-extrabold text-cloudera-navy"><Lightbulb size={14} />Insights</div>
      <ul className="mt-2 space-y-2 text-slate-700">{response.answer.insights.map(item => <li key={item} className="flex gap-2"><span className="text-cloudera-orange">•</span><span>{item}</span></li>)}</ul>
    </section>}

    {response.answer.business_implications.length > 0 && <section>
      <div className="text-xs font-extrabold text-cloudera-navy">Business implications</div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">{response.answer.business_implications.map(item => <div key={item} className="rounded-xl border border-violet-100 bg-violet-50/60 p-3 text-slate-700">{item}</div>)}</div>
    </section>}

    {response.chart_spec?.type === 'kpi' && <div className="max-w-xs"><KpiCard label={response.chart_spec.title} value={kpiValue} format="" icon={BarChart3} /></div>}
    <AnswerChart chart={response.chart_spec} rows={response.data.rows} />
    {response.data.rows.length > 0 && <div>
      {hasVisualChart && <button type="button" onClick={() => setShowTable(previous => !previous)} className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 transition-colors hover:text-cloudera-navy">
        <Table2 size={13} />{showTable ? 'Hide table detail' : 'Show table detail'}<ChevronDown size={13} className={`transition-transform ${showTable ? 'rotate-180' : ''}`} />
      </button>}
      {showTable && <div className={`overflow-hidden rounded-xl border border-slate-200 ${hasVisualChart ? 'mt-2' : ''}`}><DataTable columns={response.data.columns} rows={response.data.rows} /></div>}
    </div>}

    {(response.answer.caveats.length > 0 || dataReferenceParts) && <div className="space-y-3 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
      {response.answer.caveats.length > 0 && <div className="flex gap-2 leading-6"><Info size={14} className="mt-0.5 shrink-0" /><span>{response.answer.caveats.join(' ')}</span></div>}
      {dataReferenceParts && <div className="space-y-1.5">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Data reference</div>
        {dataReferenceParts.note && <p className="leading-6 text-slate-500">{dataReferenceParts.note}</p>}
        {dataReferenceParts.sql && <pre className="overflow-x-auto rounded-lg bg-slate-900 px-3 py-2.5 text-xs leading-5 text-slate-100"><code>{dataReferenceParts.sql}</code></pre>}
      </div>}
    </div>}

    <div className="border-t border-slate-100 pt-3 text-xs text-slate-400">{response.provider} · {response.model} · {response.strategy} · {response.timings.total_ms.toFixed(0)} ms</div>
  </div>
}

// data_reference arrives as one string, sometimes prose followed by
// "Query: <sql>" - split them so the SQL can render in a monospace code
// block instead of wrapping inline with the explanatory sentence.
function splitDataReference(value: string): { note: string | null; sql: string | null } {
  const match = value.match(/^(.*?)(?:query:\s*)(select[\s\S]+)$/i)
  if (!match) return { note: value, sql: null }
  const [, note, sql] = match
  return { note: note.trim() || null, sql: sql.trim() }
}
