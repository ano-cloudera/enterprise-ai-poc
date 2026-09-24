'use client'

import { FormEvent, KeyboardEvent, MouseEvent, useEffect, useRef, useState } from 'react'
import { ArrowUp, CheckCircle2, ChevronRight, Database, Info, Lightbulb, MessageSquareText, Plus, Trash2, UserRound } from 'lucide-react'
import { useSearchParams } from 'next/navigation'
import { AnswerChart } from '../components/AnswerChart'
import { DataTable } from '../components/DataTable'
import { ScanMark } from '../components/ScanMark'
import { api } from '../lib/api'
import { suggestedFollowUps } from '../lib/businessPresentation'
import { useDashboardState } from '../lib/dashboardState'
import { useProject } from '../lib/project'
import { formatFloatingAnswerText, formatFloatingDriver } from '../lib/floatingAnswerFormatting'
import { createSessionId, deleteSession, loadSessions, saveSession, sessionTitle, type ChatSession, type StoredMessage } from '../lib/chatSessions'
import type { ChatResponse } from '../types/api'

const starterQuestions = [
  'Kenapa sales Jawa Barat turun bulan ini?',
  'Channel mana yang paling terdampak?',
  'Produk mana yang menjadi driver utama?',
  'Bagaimana forecast bulan depan?',
]

const impalaStarterQuestions = [
  'Bagaimana tren Gross Sales selama Q4 2024?',
  'Material mana dengan Fill Rate terendah?',
  'Bagaimana rasio Sell-Out terhadap Sell-In per customer?',
  'Sales office mana dengan picking delay tertinggi selama Q4?',
]

type UIMessage = StoredMessage

export function AskAIPage() {
  const { state: dashboardState, applyDashboardAiActions } = useDashboardState()
  const { config: projectConfig } = useProject()
  const searchParams = useSearchParams()
  const initial = searchParams.get('q') || ''
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(createSessionId)
  const [messages, setMessages] = useState<UIMessage[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(false)
  const [capabilityExamples, setCapabilityExamples] = useState<string[]>([])
  const initialSubmitted = useRef(false)
  const conversationEnd = useRef<HTMLDivElement>(null)

  useEffect(() => { setSessions(loadSessions()) }, [])

  useEffect(() => {
    if (!projectConfig.semantic_capabilities_enabled) return
    api.semanticCapabilities()
      .then(response => setCapabilityExamples(Array.isArray(response.examples) ? response.examples.slice(0, 4) : []))
      .catch(() => setCapabilityExamples([]))
  }, [projectConfig.semantic_capabilities_enabled])

  useEffect(() => {
    if (!messages.length) return
    saveSession({ id: sessionId, title: sessionTitle(messages), updatedAt: Date.now(), messages })
    setSessions(loadSessions())
  }, [messages, sessionId])

  async function submit(question = input) {
    const value = question.trim()
    if (!value || loading) return
    setMessages(current => [...current, { role: 'user', content: value }])
    setInput('')
    setLoading(true)
    try {
      const response = await api.chat(value, sessionId, dashboardState)
      applyDashboardAiActions(response.ui_actions)
      setMessages(current => [...current, { role: 'assistant', content: response.answer.summary, response }])
    } catch {
      setMessages(current => [...current, { role: 'assistant', content: 'Unable to complete the analysis right now. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  function startNewChat() {
    setSessions(loadSessions())
    setSessionId(createSessionId())
    setMessages([])
    setInput('')
  }

  function openSession(session: ChatSession) {
    setSessionId(session.id)
    setMessages(session.messages)
    setInput('')
  }

  function removeSession(event: MouseEvent, id: string) {
    event.stopPropagation()
    deleteSession(id)
    setSessions(loadSessions())
    if (id === sessionId) startNewChat()
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey || !input.trim() || loading) return
    event.preventDefault()
    submit()
  }

  useEffect(() => {
    if (initialSubmitted.current) return
    initialSubmitted.current = true
    if (initial) submit(initial)
  }, [])

  useEffect(() => {
    if (!messages.length && !loading) return
    conversationEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])

  const semanticMode = projectConfig.semantic_capabilities_enabled
  const activeStarterQuestions = semanticMode
    ? (capabilityExamples.length ? capabilityExamples : impalaStarterQuestions)
    : starterQuestions

  return (
    <div className="flex h-[calc(100dvh-112px)] min-w-0 flex-col sm:h-[calc(100dvh-128px)] xl:h-[calc(100dvh-136px)] 2xl:h-[calc(100dvh-144px)]">
      <div className="grid min-h-0 min-w-0 flex-1 gap-4 xl:grid-cols-[214px_minmax(0,1fr)]">
        <aside className="card hidden h-full min-w-0 overflow-y-auto p-4 xl:block">
          <button type="button" onClick={startNewChat} className="btn-primary w-full"><Plus size={16} />New Chat</button>
          <div className="mt-6 text-sm font-extrabold text-cloudera-navy">Recent conversations</div>
          {sessions.length ? (
            <div className="mt-3 space-y-2">{sessions.map(session => (
              <div key={session.id} className={`group relative w-full rounded-xl border transition hover:bg-slate-50 ${session.id === sessionId ? 'border-orange-200 bg-orange-50/60' : 'border-transparent text-slate-600'}`}>
                <button type="button" onClick={() => openSession(session)} className="w-full p-3 pr-9 text-left text-xs leading-5">
                  <div className="flex gap-2"><MessageSquareText size={15} className="mt-0.5 shrink-0 text-slate-400" /><span className="min-w-0 break-words font-semibold">{session.title}</span></div>
                  <div className="ml-6 mt-1 text-[10px] text-slate-400">{new Date(session.updatedAt).toLocaleString()}</div>
                </button>
                <button type="button" onClick={event => removeSession(event, session.id)} aria-label="Delete conversation" className="absolute right-2 top-2.5 grid h-6 w-6 place-items-center rounded-lg text-slate-300 opacity-0 transition hover:bg-rose-50 hover:text-rose-500 group-hover:opacity-100"><Trash2 size={13} /></button>
              </div>
            ))}</div>
          ) : <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs text-slate-500">No conversations yet.</div>}
        </aside>

        <section className="card order-1 flex h-full min-h-0 min-w-0 flex-col overflow-hidden xl:order-none">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
            <div className="flex items-center gap-2"><ScanMark size={32} /><div><div className="text-sm font-extrabold text-cloudera-navy">SCAN</div><div className="text-[11px] text-emerald-600">● Connected to governed data</div></div></div>
            <div className="chip"><Database size={13} />{semanticMode ? 'Impala · Q4 2024' : 'Governed Data'}</div>
          </div>

          <div role="log" aria-label="Conversation" aria-live="polite" className={`min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top_right,rgba(99,91,255,.04),transparent_30%),radial-gradient(circle_at_bottom_left,rgba(255,90,31,.05),transparent_30%)] p-4 sm:p-5 ${messages.length === 0 ? 'flex' : 'space-y-5'}`}>
            {messages.length === 0 && (
              <div className="m-auto w-full max-w-3xl text-center">
                <ScanMark size={56} className="mx-auto" rounded="2xl" />
                <h2 className="mt-5 text-2xl font-black text-cloudera-navy">{semanticMode ? 'Ask SCAN about TEMPO Q4 2024' : 'Ask your commercial data'}</h2>
                <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-500">{semanticMode ? 'I can help with governed Sell-In, Sell-Out, Material 360, Service Level, warehouse stock, sales office, and shared-customer reconciliation. Unsupported questions are qualified rather than guessed.' : 'Ask a management question to get a concise answer, supporting evidence, and practical next steps.'}</p>
                <div className="mt-7 grid gap-3 sm:grid-cols-2">{activeStarterQuestions.map(item => <button type="button" onClick={() => submit(item)} key={item} className="rounded-xl border border-slate-200 bg-white p-5 text-left text-sm font-semibold text-slate-600 shadow-sm transition hover:border-orange-200 hover:text-cloudera-navy">{item}<ChevronRight className="mt-2.5 text-cloudera-orange" size={14} /></button>)}</div>
              </div>
            )}
            {messages.map((message, index) => message.role === 'user' ? (
              <div key={index} className="ml-auto flex max-w-[90%] items-start justify-end gap-2 sm:max-w-[600px]"><div className="min-w-0 break-words rounded-2xl rounded-tr-md bg-cloudera-navy px-4 py-3 text-sm leading-6 text-white">{message.content}</div><div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-200 text-slate-600"><UserRound size={15} /></div></div>
            ) : (
              <div key={index} className="flex min-w-0 items-start gap-3"><ScanMark size={36} /><div className="min-w-0 max-w-[760px] flex-1 rounded-2xl rounded-tl-md border border-slate-200 bg-white p-4 shadow-sm sm:p-5">{message.response ? <StructuredAnswer response={message.response} onSelectFollowUp={submit} /> : <div className="text-sm leading-6 text-slate-700">{message.content}</div>}</div></div>
            ))}
            {loading && <div className="flex items-center gap-3"><ScanMark size={36} /><div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs font-semibold text-slate-500"><span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-cloudera-orange" />Analyzing governed data...</div></div>}
            <div ref={conversationEnd} aria-hidden="true" />
          </div>

          <form onSubmit={(event: FormEvent) => { event.preventDefault(); submit() }} className="border-t border-slate-200 bg-white p-4">
            <div className="flex items-end gap-2 rounded-2xl border border-slate-200 p-2 shadow-sm focus-within:border-cloudera-violet focus-within:ring-4 focus-within:ring-cloudera-violet/10">
              <textarea value={input} onChange={event => setInput(event.target.value)} onKeyDown={handleComposerKeyDown} rows={2} placeholder="Ask a follow-up question..." className="min-h-[48px] min-w-0 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none" />
              <button type="submit" disabled={loading || !input.trim()} aria-label="Send question" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cloudera-orange text-white disabled:opacity-40"><ArrowUp size={18} /></button>
            </div>
            <div className="mt-2 text-[10px] text-slate-400">AI-generated insights should be reviewed alongside your business context.</div>
          </form>
        </section>

      </div>
    </div>
  )
}

function StructuredAnswer({ response, onSelectFollowUp }: { response: ChatResponse; onSelectFollowUp: (question: string) => void }) {
  const drivers = response.answer.drivers.map(formatFloatingDriver).filter(Boolean).slice(0, 3)
  const actions = response.answer.recommended_actions.slice(0, 3)
  const caveats = response.answer.caveats.slice(0, 3)
  // Whether to show the table is this message's own concern - drawn from
  // its own ui_actions, never from the shared dashboard state.chat.table
  // flag. That flag (and its .columns) is a single global value shared by
  // every message in the conversation, so using it here made an earlier
  // question's table silently render with a later question's column
  // headers (or vice versa) once more than one analytical answer existed
  // in the same session.
  const showTable = response.ui_actions.some(action => action.type === 'SHOW_TABLE') && response.data.rows.length > 0
  const showChart = Boolean(response.chart_spec && response.chart_spec.type !== 'none' && response.chart_spec.type !== 'table')
  const followUps = suggestedFollowUps(response.metadata.intent).slice(0, 3)

  if (response.metadata.intent === 'conversational') {
    return <p aria-label="AI response" className="min-w-0 break-words text-sm leading-6 text-slate-700">{formatFloatingAnswerText(response.answer.summary)}</p>
  }

  return (
    <div aria-label="AI response" className="min-w-0">
      <section>
        <div className="text-xs font-extrabold text-cloudera-navy">Executive Summary</div>
        <p className="mt-2 break-words text-sm leading-6 text-slate-700">{formatFloatingAnswerText(response.answer.summary)}</p>
      </section>
      {drivers.length > 0 && <section className="mt-5"><div className="text-xs font-extrabold text-cloudera-navy">Key Drivers</div><div className="mt-2 space-y-2">{drivers.map((item, index) => <div key={`${item}-${index}`} className="flex gap-2.5 text-sm leading-6 text-slate-700"><span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-violet-50 text-[10px] font-black text-cloudera-violet">{index + 1}</span><span className="min-w-0 break-words">{item}</span></div>)}</div></section>}
      {(showChart || showTable) && <section className="mt-5"><div className="text-xs font-extrabold text-cloudera-navy">Supporting Evidence</div>{showChart && <AnswerChart chart={response.chart_spec} />}{showTable && <DataTable columns={response.data.columns} rows={response.data.rows} metric={response.metadata.resolved_context.metric} unitFormat={response.data.unit_format} />}</section>}
      {actions.length > 0 && <section className="mt-5 rounded-2xl border border-orange-100 bg-orange-50/60 p-4"><div className="flex items-center gap-2 text-xs font-extrabold text-cloudera-navy"><Lightbulb size={15} className="text-cloudera-orange" />Recommended Actions</div><div className="mt-2 space-y-2">{actions.map((item, index) => <div key={`${item}-${index}`} className="flex gap-2 text-sm leading-6 text-slate-700"><CheckCircle2 size={15} className="mt-1 shrink-0 text-emerald-500" /><span className="min-w-0 break-words">{formatFloatingAnswerText(item)}</span></div>)}</div></section>}
      {caveats.length > 0 && <section className="mt-4 flex gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3"><Info size={14} className="mt-0.5 shrink-0 text-slate-400" /><div className="space-y-1 text-xs leading-5 text-slate-500">{caveats.map((item, index) => <p key={`${item}-${index}`} className="break-words">{formatFloatingAnswerText(item)}</p>)}</div></section>}
      <div role="group" aria-label="Suggested follow-up questions" className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
        {followUps.map(question => <button type="button" key={question} onClick={() => onSelectFollowUp(question)} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-[11px] font-semibold leading-4 text-slate-600 transition hover:border-orange-200 hover:bg-orange-50 hover:text-cloudera-navy">{question}</button>)}
      </div>
    </div>
  )
}
