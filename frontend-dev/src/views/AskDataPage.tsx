'use client'

import { MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BarChart3, ChevronDown, Lightbulb, Table2 } from 'lucide-react'
import { ChatComposer } from '../components/ChatComposer'
import { DataNote } from '../components/DataNote'
import { ResponseFooter } from '../components/ResponseFooter'
import { StreamingProgress } from '../components/StreamingProgress'
import { appConfig } from '../config/appConfig'
import { downloadConversationPdf } from '../lib/chatPdfExport'
import { clarificationChoices } from '../lib/clarificationPrompts'
import { answerPresentation, hasGovernedEvidence } from '../lib/governedEvidence'
import { AnswerChart } from '../components/AnswerChart'
import { AnswerProse } from '../components/AnswerProse'
import { DataTable } from '../components/DataTable'
import { SingleRowEvidence } from '../components/SingleRowEvidence'
import { compactSingleRowEvidence } from '../lib/singleRowPresentation'
import { KpiCard } from '../components/KpiCard'
import {
  AssistantContent,
  ConversationInner,
  USER_BUBBLE_CLASS,
  USER_MESSAGE_ROW_CLASS,
} from '../components/ConversationInner'
import { EmptyStateLogo } from '../components/EmptyStateLogo'
import { api } from '../lib/api'
import { mergeDataNotes, parseDataProvenance } from '../lib/dataProvenance'
import {
  createSessionId,
  deleteSession,
  loadSessions,
  saveSession,
  sessionTitle,
  renameSession,
  toggleSessionPinned,
  type ChatSession,
  type ProcessSnapshot,
  type StoredMessage,
} from '../lib/chatSessions'
import { useModelSelection } from '../lib/modelSelection'
import { useChatLayout } from '../layout/AppShell'
import {
  DETAILED_PROGRESS_STEPS,
  mergeProgressStep,
  type ProgressTraceEntry,
} from '../lib/streamProgress'
import { AnalysisReportPanel } from '../components/AnalysisReportPanel'
import { AnalysisSplitHandle } from '../components/AnalysisSplitHandle'
import { useReportSplitPane } from '../lib/useReportSplitPane'
import { ReportArtifactCard } from '../components/ReportArtifactCard'
import {
  reportSectionTitle,
  reportSectionsFromMessages,
  responseHasReportEvidence,
} from '../lib/reportDocument'
import type { ChatResponse, SuggestedQuestion } from '../types/api'

const STARTER_QUESTION_COUNT = 3

export function AskDataPage() {
  const { setChatSessionSidebar, setChatPageChrome } = useChatLayout()
  const { selection, select, loading: modelsLoading, error: modelError } = useModelSelection()
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(createSessionId)
  const [messages, setMessages] = useState<StoredMessage[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const [technicalTrace, setTechnicalTrace] = useState<ProgressTraceEntry[]>([])
  const [error, setError] = useState('')
  const [starterQuestions, setStarterQuestions] = useState<SuggestedQuestion[]>([])
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [pdfExportPreview, setPdfExportPreview] = useState(false)
  const [reportPanelOpen, setReportPanelOpen] = useState(false)
  const [activeReportSectionId, setActiveReportSectionId] = useState<string | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const conversationExportRef = useRef<HTMLDivElement>(null)
  const activeRequest = useRef<AbortController | null>(null)
  const progressLiveRef = useRef({ step: 0, trace: [] as ProgressTraceEntry[] })

  useEffect(() => setSessions(loadSessions()), [])
  useEffect(() => { if (messages.length) { saveSession({ id: sessionId, title: sessionTitle(messages), updatedAt: Date.now(), messages, selection: selection || undefined }); setSessions(loadSessions()) } }, [messages, selection, sessionId])
  useEffect(() => { end.current?.scrollIntoView?.({ behavior: 'smooth' }) }, [messages, loading, progressStep])
  useEffect(() => () => activeRequest.current?.abort(), [])
  useEffect(() => { api.randomQueries(STARTER_QUESTION_COUNT).then(response => setStarterQuestions(response.questions)).catch(() => setStarterQuestions([])) }, [])

  const reportSections = useMemo(() => reportSectionsFromMessages(messages), [messages])
  const activeReportSection = useMemo(() => {
    if (activeReportSectionId) {
      return reportSections.find(s => s.id === activeReportSectionId) ?? reportSections[reportSections.length - 1]
    }
    return reportSections[reportSections.length - 1]
  }, [reportSections, activeReportSectionId])

  const reportDocumentTitle = useMemo(() => {
    if (activeReportSection) return reportSectionTitle(activeReportSection.response)
    return appConfig.reportDocumentLabel
  }, [activeReportSection])

  const canUseReportPanel = appConfig.analysisReportPanel && reportSections.length > 0
  const panelActive = canUseReportPanel && reportPanelOpen

  const { containerRef, chatColumnRef, beginResize, moveResize, endResize, isDragging, chatStyle, paneStyle } =
    useReportSplitPane(canUseReportPanel)

  async function submit(question = input) {
    const value = question.trim()
    if (!value || loading || !selection) return
    setMessages(current => [...current, { role: 'user', content: value }])
    setInput('')
    setError('')
    setLoading(true)
    setProgressStep(0)
    setTechnicalTrace([])
    progressLiveRef.current = { step: 0, trace: [] }
    const controller = new AbortController()
    activeRequest.current = controller
    let timedOut = false
    const streamTimeoutMs = Number(process.env.NEXT_PUBLIC_CHAT_STREAM_TIMEOUT_MS || 180_000)
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort() }, streamTimeoutMs)
    let streamSucceeded = false
    try {
      for await (const event of api.chatStream(value, sessionId, selection, controller.signal)) {
        if (event.type === 'progress') {
          setProgressStep(current => {
            const next = mergeProgressStep(current, event.stage, event.label)
            progressLiveRef.current.step = next
            return next
          })
          setTechnicalTrace(current => {
            const entry: ProgressTraceEntry = { stage: event.stage, label: event.label, detail: event.detail }
            const key = `${entry.stage}|${entry.label}|${entry.detail ?? ''}`
            const last = current[current.length - 1]
            const lastKey = last ? `${last.stage}|${last.label}|${last.detail ?? ''}` : ''
            if (key === lastKey) return current
            const next = [...current, entry]
            progressLiveRef.current.trace = next
            return next
          })
          continue
        }
        if (event.type === 'done') {
          streamSucceeded = true
          const finalStep = Math.max(
            progressLiveRef.current.step,
            DETAILED_PROGRESS_STEPS.length - 1,
          )
          const processSnapshot: ProcessSnapshot = {
            activeStepIndex: finalStep,
            technicalTrace: [...progressLiveRef.current.trace],
          }
          setMessages(current => [
            ...current,
            {
              role: 'assistant',
              content: event.response.answer.executive_summary,
              response: event.response,
              processSnapshot,
            },
          ])
          if (
            appConfig.analysisReportPanel &&
            event.response.status === 'SUCCESS' &&
            responseHasReportEvidence(event.response)
          ) {
            setReportPanelOpen(true)
            setActiveReportSectionId(event.response.request_id)
          }
        }
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
      setLoading(false)
      if (!streamSucceeded) {
        setProgressStep(0)
        setTechnicalTrace([])
      }
    }
  }

  function stopRequest() { activeRequest.current?.abort() }

  const newChat = useCallback(() => {
    setSessionId(createSessionId())
    setMessages([])
    setInput('')
    setError('')
    setReportPanelOpen(false)
    setActiveReportSectionId(null)
  }, [])

  const openReportSection = useCallback((requestId: string) => {
    setActiveReportSectionId(requestId)
    setReportPanelOpen(true)
  }, [])

  const openSession = useCallback(
    (session: ChatSession) => {
      setSessionId(session.id)
      setMessages(session.messages)
      setInput('')
      if (session.selection) select(session.selection)
    },
    [select],
  )

  const removeSession = useCallback(
    (event: MouseEvent, id: string) => {
      event.stopPropagation()
      deleteSession(id)
      void api.deleteChatSession(id).catch(() => undefined)
      setSessions(loadSessions())
      if (id === sessionId) newChat()
    },
    [sessionId, newChat],
  )

  const togglePinSession = useCallback((event: MouseEvent, id: string) => {
    event.stopPropagation()
    setSessions(toggleSessionPinned(id))
  }, [])

  const handleRenameSession = useCallback((id: string, title: string) => {
    setSessions(renameSession(id, title))
  }, [])

  useEffect(() => {
    setChatSessionSidebar({
      sessions,
      activeSessionId: sessionId,
      onNewChat: newChat,
      onOpenSession: openSession,
      onRemoveSession: removeSession,
      onTogglePinSession: togglePinSession,
      onRenameSession: handleRenameSession,
    })
    return () => setChatSessionSidebar(null)
  }, [
    sessions,
    sessionId,
    newChat,
    openSession,
    removeSession,
    togglePinSession,
    handleRenameSession,
    setChatSessionSidebar,
  ])

  const downloadChat = useCallback(async () => {
    if (!messages.length || downloadingPdf) return
    const root = conversationExportRef.current
    setDownloadingPdf(true)
    setError('')
    setPdfExportPreview(true)
    await new Promise<void>(resolve => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
    })
    try {
      await downloadConversationPdf({
        title: sessionTitle(messages),
        messages,
        appName: appConfig.headerTitle,
        chartRoot: root,
      })
    } catch (err) {
      console.error('conversation_pdf_export_failed', err)
      setError('Unable to generate PDF. Please try again.')
    } finally {
      setPdfExportPreview(false)
      setDownloadingPdf(false)
    }
  }, [messages, downloadingPdf])

  useEffect(() => {
    setChatPageChrome({
      showDownload: messages.length > 0,
      downloadingPdf,
      loading,
      minimalHeader: messages.length === 0 && !loading,
      onDownloadPdf: () => void downloadChat(),
    })
    return () => setChatPageChrome(null)
  }, [messages.length, downloadingPdf, loading, downloadChat, setChatPageChrome])

  const modelHint =
    modelsLoading || modelError || !selection
      ? modelsLoading
        ? 'Discovering configured models…'
        : modelError || 'No configured model is available. Open Settings or contact the operator.'
      : null

  useEffect(() => {
    if (reportSections.length === 0) setReportPanelOpen(false)
  }, [reportSections.length])

  return (
    <div
      ref={containerRef}
      data-split-dragging={isDragging ? 'true' : 'false'}
      className="flex h-full min-h-0 w-full flex-1 overflow-hidden pb-14 lg:pb-0"
    >
      <div
        ref={chatColumnRef}
        data-split-chat
        style={panelActive ? chatStyle : { flex: '1 1 0%', minWidth: 0, width: 'auto' }}
        className={`split-pane-chat flex h-full min-h-0 min-w-0 flex-col overflow-hidden ${
          panelActive ? '' : 'min-w-0 flex-1'
        }`}
      >
      <div
        role="log"
        aria-label="Conversation"
        className={`scrollbar-pane min-h-0 flex-1 overflow-y-scroll overscroll-contain py-4 ${messages.length || loading ? '' : 'flex'}`}
      >
        <ConversationInner className={messages.length || loading ? 'space-y-6' : 'flex flex-1 flex-col justify-center'}>
            {!messages.length && (
              <div className="mx-auto w-full max-w-xl text-center">
                <EmptyStateLogo />
                <h1 className="type-app-title mt-5 text-xl">{appConfig.emptyStateTitle}</h1>
                <p className="type-chat-body mt-2.5 text-slate-500">{appConfig.emptyStateDescription}</p>
                {starterQuestions.length > 0 && (
                  <div className="mt-7 text-left">
                    <p className="mb-2.5 text-sm font-medium text-cloudera-navy">
                      {appConfig.starterQuestionsCaption}
                    </p>
                    <div className="grid gap-2 sm:grid-cols-3">
                    {starterQuestions.map(item => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => submit(item.question)}
                        disabled={!selection || loading}
                        className="rounded-xl border border-slate-200 bg-white p-3 text-left text-sm leading-5 text-slate-600 transition-colors hover:border-cloudera-orange/40 hover:bg-orange-50/40 disabled:opacity-50"
                      >
                        {item.question}
                      </button>
                    ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            <div ref={conversationExportRef} className={messages.length ? 'space-y-6' : undefined}>
              {messages.map((message, index) =>
                message.role === 'user' ? (
                  <div key={index} className={USER_MESSAGE_ROW_CLASS}>
                    <div className={USER_BUBBLE_CLASS}>{message.content}</div>
                  </div>
                ) : (
                  <AssistantContent key={index}>
                    {message.response ? (
                      <StructuredAnswer
                        response={message.response}
                        processSnapshot={message.processSnapshot}
                        expandForExport={pdfExportPreview}
                        onClarificationPick={text => submit(text)}
                        clarificationDisabled={loading}
                        reportArtifact={
                          appConfig.analysisReportPanel &&
                          message.response.status === 'SUCCESS' &&
                          responseHasReportEvidence(message.response)
                            ? {
                                title: reportSectionTitle(message.response),
                                active: activeReportSectionId === message.response.request_id,
                                onOpen: () => openReportSection(message.response!.request_id),
                              }
                            : undefined
                        }
                      />
                    ) : (
                      <p className="type-chat-body text-slate-700">{message.content}</p>
                    )}
                  </AssistantContent>
                ),
              )}
            </div>
            {loading && (
              <StreamingProgress activeStepIndex={progressStep} technicalTrace={technicalTrace} />
            )}
            {error && (
              <AssistantContent>
                <div className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</div>
              </AssistantContent>
            )}
            <div ref={end} />
        </ConversationInner>
      </div>

      <div className="z-10 shrink-0 border-t border-slate-200/80 bg-cloudera-mist/95 pb-1 pt-3 backdrop-blur-[3px]">
        <ConversationInner>
          <ChatComposer
            value={input}
            loading={loading}
            disabled={!selection}
            modelHint={modelHint}
            onChange={setInput}
            onSubmit={() => submit()}
            onStop={stopRequest}
          />
        </ConversationInner>
      </div>
      </div>

      {canUseReportPanel && (
        <>
          {panelActive ? (
            <AnalysisSplitHandle
              onResizeStart={beginResize}
              onResizeMove={moveResize}
              onResizeEnd={endResize}
            />
          ) : null}
          <div
            data-split-panel
            className={`split-pane-panel hidden h-full min-h-0 overflow-hidden lg:flex ${
              panelActive
                ? 'min-w-0 max-w-none flex-1 opacity-100'
                : 'max-w-0 flex-[0_0_0px] opacity-0 pointer-events-none'
            }`}
            style={panelActive ? paneStyle : { width: 0, flex: '0 0 0px', maxWidth: 0 }}
          >
            <div
              className={`split-pane-panel-inner split-pane-panel-content h-full w-full min-w-[420px] ${
                panelActive ? 'translate-x-0 opacity-100' : 'translate-x-4 opacity-0'
              }`}
            >
              <AnalysisReportPanel
                open
                onClose={() => setReportPanelOpen(false)}
                documentTitle={reportDocumentTitle}
                userQuestion={activeReportSection?.userQuestion ?? ''}
                sections={reportSections}
                activeSectionId={activeReportSectionId}
                onExportPdf={() => void downloadChat()}
                exportingPdf={downloadingPdf}
              />
            </div>
          </div>
        </>
      )}
      {appConfig.analysisReportPanel && reportPanelOpen && reportSections.length > 0 && (
        <div className="fixed inset-x-0 bottom-14 z-30 max-h-[70vh] px-3 lg:hidden">
          <AnalysisReportPanel
            open={reportPanelOpen}
            onClose={() => setReportPanelOpen(false)}
            documentTitle={reportDocumentTitle}
            userQuestion={activeReportSection?.userQuestion ?? ''}
            sections={reportSections}
            activeSectionId={activeReportSectionId}
            onExportPdf={() => void downloadChat()}
            exportingPdf={downloadingPdf}
          />
        </div>
      )}
    </div>
  )
}

function StructuredAnswer({
  response,
  processSnapshot,
  expandForExport = false,
  onClarificationPick,
  clarificationDisabled = false,
  reportArtifact,
}: {
  response: ChatResponse
  processSnapshot?: ProcessSnapshot
  expandForExport?: boolean
  onClarificationPick?: (text: string) => void
  clarificationDisabled?: boolean
  reportArtifact?: { title: string; active: boolean; onOpen: () => void }
}) {
  const presentation = answerPresentation(response)
  const missingGovernedEvidence = response.status === 'SUCCESS' && response.strategy === 'governed' && !hasGovernedEvidence(response)
  const kpiField = response.chart_spec?.type === 'kpi' ? response.chart_spec.y || response.data.columns[0] : null
  const kpiValue = kpiField ? response.data.rows[0]?.[kpiField] : undefined
  const visualChartTypes = ['bar', 'line', 'area', 'scatter', 'pie']
  const hasVisualChart = Boolean(
    response.chart_spec && visualChartTypes.includes(response.chart_spec.type) && response.chart_spec.x && response.chart_spec.y && response.data.rows.length > 0
  )
  const [showTable, setShowTable] = useState(!hasVisualChart)
  const showTableDetail = expandForExport || showTable
  const statusStyles: Record<Exclude<ChatResponse['status'], 'ERROR'>, string> = {
    SUCCESS: 'bg-emerald-50 text-emerald-700',
    CLARIFICATION: 'bg-amber-50 text-amber-700',
    NO_DATA: 'bg-slate-100 text-slate-600',
    UNSUPPORTED: 'bg-slate-100 text-slate-600',
  }

  const provenance = parseDataProvenance(response.answer.data_reference)
  const dataNote = mergeDataNotes(response.answer.caveats, provenance)
  const omitTablesInProse = response.data.rows.length > 0

  const showEvidenceBlock =
    response.chart_spec?.type === 'kpi' ||
    hasVisualChart ||
    response.data.rows.length > 0

  const provenanceSources = provenance?.sources ?? []
  const hasDataNoteContent = Boolean(dataNote || provenanceSources.length > 0)
  /** Welcome / prose-only: tuck note into the main card as a footnote */
  const dataNoteInNarrative = hasDataNoteContent && !showEvidenceBlock
  const chartFirst = hasVisualChart
  const compactSingleRow =
    !hasVisualChart &&
    response.chart_spec?.type !== 'kpi' &&
    response.data.rows.length === 1
      ? compactSingleRowEvidence(response.data.columns, response.data.rows)
      : null
  const showExecutiveSummary =
    response.answer.executive_summary.trim() !== response.answer.direct_answer.trim()
  const hasAnalysisBody =
    showExecutiveSummary ||
    response.answer.insights.length > 0 ||
    response.answer.business_implications.length > 0 ||
    dataNoteInNarrative

  const headerRow = (
    <div className="flex items-center justify-between gap-3">
      <div className="type-answer-kicker">{presentation.title}</div>
      {presentation.showStatusChip && presentation.statusChip && presentation.statusChip !== 'ERROR' && (
        <span className={`type-chip rounded-full px-2.5 py-0.5 ${statusStyles[presentation.statusChip]}`}>
          {presentation.statusChip}
        </span>
      )}
    </div>
  )

  const governedWarning = missingGovernedEvidence ? (
    <p className="answer-response-metadata rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
      Narasi di bawah belum terhubung ke query governed Impala (tidak ada query_id / baris data). Ulangi pertanyaan analitik atau gunakan contoh starter.
    </p>
  ) : null

  const clarificationBlock = (() => {
    const choices = clarificationChoices(response)
    if (!choices?.length || !onClarificationPick) return null
    return (
      <div className="answer-section-divider flex flex-wrap gap-2 !pt-3" role="group" aria-label="Clarification choices">
        {choices.map(choice => (
          <button
            key={choice.id}
            type="button"
            disabled={clarificationDisabled}
            onClick={() => onClarificationPick(choice.submitText)}
            className="rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 text-left text-xs font-semibold text-amber-950 transition-colors hover:border-cloudera-orange/50 hover:bg-orange-50 disabled:opacity-50"
          >
            {choice.label}
          </button>
        ))}
      </div>
    )
  })()

  const insightsBlock =
    response.answer.insights.length > 0 ? (
      <div className="answer-section-divider space-y-3">
        <div className="type-section-label flex items-center gap-2">
          <Lightbulb size={14} className="text-cloudera-orange" aria-hidden />
          Insights
        </div>
        <ul className="answer-prose-secondary space-y-2.5">
          {response.answer.insights.map(item => (
            <li key={item} className="flex gap-2">
              <span className="text-cloudera-orange" aria-hidden>
                •
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    ) : null

  const implicationsBlock =
    response.answer.business_implications.length > 0 ? (
      <div className="answer-section-divider space-y-3">
        <div className="type-section-label">Business implications</div>
        <div className="rounded-lg border border-slate-200/90 bg-slate-50/50 p-4 shadow-[inset_3px_0_0_0_rgba(154,140,255,0.55)]">
          <ul className="answer-implication-card space-y-2.5">
            {response.answer.business_implications.map(item => (
              <li key={item} className="flex gap-2">
                <span className="text-cloudera-violet/80 shrink-0" aria-hidden>
                  •
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    ) : null

  const chatDocumentSplit = Boolean(reportArtifact && !expandForExport)

  if (chatDocumentSplit) {
    const teaser = response.answer.direct_answer.trim()
    const teaserText = teaser.length > 320 ? `${teaser.slice(0, 317)}…` : teaser
    return (
      <div aria-label="AI response" className="chat-response-typography flex flex-col gap-3">
        <section className="answer-surface space-y-2">
          {headerRow}
          {governedWarning}
          <AnswerProse text={teaserText} omitTables={omitTablesInProse} variant="main" />
          {clarificationBlock}
        </section>
        <ReportArtifactCard
          title={reportArtifact!.title}
          subtitle={appConfig.reportDocumentLabel}
          active={reportArtifact!.active}
          onOpen={reportArtifact!.onOpen}
        />
        <ResponseFooter
          response={response}
          processSnapshot={processSnapshot}
          variant="inline"
          metadataClassName="answer-response-metadata"
        />
      </div>
    )
  }

  const evidenceBlock = showEvidenceBlock ? (
    <section className={`answer-surface ${hasVisualChart ? 'space-y-0' : 'space-y-3'}`}>
      {response.chart_spec?.type === 'kpi' && (
        <div className="max-w-md">
          <KpiCard label={response.chart_spec.title} value={kpiValue} format="" icon={BarChart3} />
        </div>
      )}

      {hasVisualChart && (
        <AnswerChart chart={response.chart_spec} rows={response.data.rows} embedded className="!mb-0" />
      )}

      {response.data.rows.length > 0 && (
        <div className={hasVisualChart ? 'answer-section-divider-compact -mt-2 space-y-1 !pb-0' : 'space-y-3'}>
          {!hasVisualChart && !compactSingleRow && <div className="type-section-label">Data table</div>}
          {!hasVisualChart && compactSingleRow && <div className="type-section-label">Key figure</div>}
          {hasVisualChart && !expandForExport && (
            <button
              type="button"
              onClick={() => setShowTable(previous => !previous)}
              className="answer-table-toggle -mx-1 flex w-full items-center gap-1.5 rounded-lg px-1 py-1 text-left transition-colors hover:bg-slate-50 hover:text-cloudera-navy"
            >
              <Table2 size={13} className="text-cloudera-orange" aria-hidden />
              {showTable ? 'Hide table detail' : 'Show table detail'}
              <ChevronDown size={13} className={`ml-auto transition-transform ${showTable ? 'rotate-180' : ''}`} />
            </button>
          )}
          {showTableDetail &&
            (compactSingleRow && !hasVisualChart ? (
              <SingleRowEvidence
                compact={compactSingleRow}
                metric={response.data.governed_metric ?? undefined}
                unitFormat={response.data.unit_format ?? undefined}
                title={response.chart_spec?.title ?? undefined}
              />
            ) : (
              <div className="overflow-hidden rounded-lg border border-slate-200/90 bg-white">
                <DataTable
                  columns={response.data.columns}
                  rows={response.data.rows}
                  metric={response.data.governed_metric ?? undefined}
                  unitFormat={response.data.unit_format ?? undefined}
                />
              </div>
            ))}
        </div>
      )}
    </section>
  ) : null

  return (
    <div aria-label="AI response" className="chat-response-typography flex flex-col gap-4">
      <section className="answer-surface space-y-3">
        {headerRow}
        {governedWarning}
        <div className="space-y-2">
          <AnswerProse text={response.answer.direct_answer} omitTables={omitTablesInProse} variant="main" />
          {!chartFirst && showExecutiveSummary && (
            <AnswerProse text={response.answer.executive_summary} omitTables={omitTablesInProse} variant="support" />
          )}
        </div>
        {clarificationBlock}
        {!chartFirst && (
          <>
            {insightsBlock}
            {implicationsBlock}
            {dataNoteInNarrative && (
              <div className="answer-section-divider !pt-3">
                <DataNote note={dataNote} sources={provenanceSources} inChatResponse />
              </div>
            )}
          </>
        )}
      </section>

      {evidenceBlock}

      {chartFirst && hasAnalysisBody && (
        <section className="answer-surface space-y-3">
          {showExecutiveSummary && (
            <AnswerProse text={response.answer.executive_summary} omitTables={omitTablesInProse} variant="support" />
          )}
          {insightsBlock}
          {implicationsBlock}
          {dataNoteInNarrative && (
            <div className={showExecutiveSummary || insightsBlock || implicationsBlock ? 'answer-section-divider !pt-3' : ''}>
              <DataNote note={dataNote} sources={provenanceSources} inChatResponse />
            </div>
          )}
        </section>
      )}

      {reportArtifact && (
        <ReportArtifactCard
          title={reportArtifact.title}
          subtitle={appConfig.reportDocumentLabel}
          active={reportArtifact.active}
          onOpen={reportArtifact.onOpen}
        />
      )}

      <div className={`answer-meta-stack ${dataNoteInNarrative ? 'answer-meta-stack-flush' : ''}`}>
        {hasDataNoteContent && !dataNoteInNarrative && (
          <DataNote note={dataNote} sources={provenanceSources} inChatResponse />
        )}
        <ResponseFooter
          response={response}
          processSnapshot={processSnapshot}
          variant="inline"
          metadataClassName="answer-response-metadata"
        />
      </div>
    </div>
  )
}
