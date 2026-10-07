import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import type { ChatResponse } from '../types/api'
import type { StoredMessage } from './chatSessions'
import { formatAnswerParagraphs } from './answerFormatting'
import { answerPresentation } from './governedEvidence'

const A4_WIDTH_MM = 210
const A4_HEIGHT_MM = 297
const MARGIN_MM = 16
const FOOTER_Y_MM = A4_HEIGHT_MM - 10
const CONTENT_WIDTH_MM = A4_WIDTH_MM - MARGIN_MM * 2
const MAX_TABLE_ROWS = 35
const MAX_CELL_CHARS = 48
const CHART_CAPTURE_WIDTH_PX = 720

const INK: [number, number, number] = [18, 0, 94]
const ORANGE: [number, number, number] = [249, 103, 2]
const MUTED: [number, number, number] = [100, 116, 139]
const SLATE: [number, number, number] = [51, 65, 85]
const LINE: [number, number, number] = [230, 228, 238]

type JsPdfWithAutoTable = jsPDF & { lastAutoTable?: { finalY: number } }

export function conversationPdfFilename(title: string): string {
  const safeTitle = title.replace(/[^\w\s-]+/g, '').trim().replace(/\s+/g, '-').slice(0, 48) || 'conversation'
  const stamp = new Date().toISOString().slice(0, 10)
  return `tempo-scan-${safeTitle}-${stamp}.pdf`
}

export type ConversationPdfInput = {
  title: string
  messages: StoredMessage[]
  appName?: string
  /** Live DOM root used to snapshot Recharts blocks (optional). */
  chartRoot?: HTMLElement | null
}

type PdfCursor = { y: number }

function formatExportTimestamp(date: Date): string {
  return date.toLocaleString('id-ID', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function formatCellValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toLocaleString('id-ID', { maximumFractionDigits: 2 })
  }
  const text = String(value).replace(/\s+/g, ' ').trim()
  if (text.length <= MAX_CELL_CHARS) return text
  return `${text.slice(0, MAX_CELL_CHARS - 1)}…`
}

function ensureSpace(pdf: jsPDF, cursor: PdfCursor, neededMm: number, drawRunningHeader?: () => void): void {
  if (cursor.y + neededMm <= FOOTER_Y_MM - 4) return
  pdf.addPage()
  cursor.y = MARGIN_MM + 6
  drawRunningHeader?.()
}

function drawPageFooters(pdf: jsPDF, appName: string): void {
  const total = pdf.getNumberOfPages()
  for (let page = 1; page <= total; page += 1) {
    pdf.setPage(page)
    pdf.setDrawColor(...LINE)
    pdf.setLineWidth(0.2)
    pdf.line(MARGIN_MM, FOOTER_Y_MM - 4, A4_WIDTH_MM - MARGIN_MM, FOOTER_Y_MM - 4)
    pdf.setFont('helvetica', 'normal')
    pdf.setFontSize(8)
    pdf.setTextColor(...MUTED)
    pdf.text(appName, MARGIN_MM, FOOTER_Y_MM)
    pdf.text(`Page ${page} of ${total}`, A4_WIDTH_MM - MARGIN_MM, FOOTER_Y_MM, { align: 'right' })
  }
}

function drawDocumentHeader(
  pdf: jsPDF,
  cursor: PdfCursor,
  title: string,
  appName: string,
  exportedAt: Date,
  compact = false,
): void {
  const startY = cursor.y
  if (!compact) {
    pdf.setFillColor(...ORANGE)
    pdf.rect(MARGIN_MM, startY, CONTENT_WIDTH_MM, 1.2, 'F')
    cursor.y = startY + 5
    pdf.setFont('helvetica', 'bold')
    pdf.setFontSize(16)
    pdf.setTextColor(...INK)
    pdf.text(appName, MARGIN_MM, cursor.y)
    cursor.y += 7
    pdf.setFont('helvetica', 'normal')
    pdf.setFontSize(9)
    pdf.setTextColor(...MUTED)
    pdf.text(`Exported ${formatExportTimestamp(exportedAt)}`, MARGIN_MM, cursor.y)
    cursor.y += 5
  } else {
    pdf.setFont('helvetica', 'bold')
    pdf.setFontSize(10)
    pdf.setTextColor(...INK)
    pdf.text(appName, MARGIN_MM, cursor.y)
    cursor.y += 5
  }

  pdf.setFont('helvetica', 'bold')
  pdf.setFontSize(compact ? 11 : 13)
  pdf.setTextColor(...SLATE)
  const titleLines = pdf.splitTextToSize(title, CONTENT_WIDTH_MM) as string[]
  pdf.text(titleLines, MARGIN_MM, cursor.y)
  cursor.y += titleLines.length * 5 + (compact ? 4 : 6)

  pdf.setDrawColor(...LINE)
  pdf.setLineWidth(0.3)
  pdf.line(MARGIN_MM, cursor.y, A4_WIDTH_MM - MARGIN_MM, cursor.y)
  cursor.y += compact ? 6 : 8
}

function drawSectionLabel(pdf: jsPDF, cursor: PdfCursor, label: string): void {
  pdf.setFont('helvetica', 'bold')
  pdf.setFontSize(9)
  pdf.setTextColor(...ORANGE)
  pdf.text(label.toUpperCase(), MARGIN_MM, cursor.y)
  cursor.y += 5
}

function drawBodyText(
  pdf: jsPDF,
  cursor: PdfCursor,
  text: string,
  options: { fontSize?: number; bold?: boolean; color?: [number, number, number]; indent?: number } = {},
  drawRunningHeader?: () => void,
): void {
  const fontSize = options.fontSize ?? 10
  const indent = options.indent ?? 0
  const width = CONTENT_WIDTH_MM - indent
  pdf.setFont('helvetica', options.bold ? 'bold' : 'normal')
  pdf.setFontSize(fontSize)
  pdf.setTextColor(...(options.color ?? SLATE))
  const lines = pdf.splitTextToSize(text, width) as string[]
  const lineHeight = fontSize * 0.45 + 1.8
  for (const line of lines) {
    ensureSpace(pdf, cursor, lineHeight + 2, drawRunningHeader)
    pdf.text(line, MARGIN_MM + indent, cursor.y)
    cursor.y += lineHeight
  }
  cursor.y += 2
}

function drawBulletList(pdf: jsPDF, cursor: PdfCursor, items: string[], drawRunningHeader?: () => void): void {
  for (const item of items) {
    drawBodyText(pdf, cursor, `• ${item}`, { indent: 2 }, drawRunningHeader)
  }
}

function drawUserTurn(
  pdf: jsPDF,
  cursor: PdfCursor,
  question: string,
  turnIndex: number,
  drawRunningHeader: () => void,
): void {
  ensureSpace(pdf, cursor, 18, drawRunningHeader)
  drawSectionLabel(pdf, cursor, `Question ${turnIndex}`)
  pdf.setFont('helvetica', 'normal')
  pdf.setFontSize(10)
  const lines = pdf.splitTextToSize(question, CONTENT_WIDTH_MM - 8) as string[]
  const boxHeight = lines.length * 5 + 8
  ensureSpace(pdf, cursor, boxHeight + 4, drawRunningHeader)
  const boxTop = cursor.y - 3
  pdf.setFillColor(255, 247, 237)
  pdf.setDrawColor(...ORANGE)
  pdf.setLineWidth(0.25)
  pdf.roundedRect(MARGIN_MM, boxTop, CONTENT_WIDTH_MM, boxHeight, 2, 2, 'FD')
  pdf.setTextColor(...INK)
  let textY = cursor.y + 3
  for (const line of lines) {
    pdf.text(line, MARGIN_MM + 4, textY)
    textY += 5
  }
  cursor.y = boxTop + boxHeight + 6
}

function drawProseBlocks(
  pdf: jsPDF,
  cursor: PdfCursor,
  text: string,
  omitTables: boolean,
  drawRunningHeader: () => void,
  emphasisFirst = false,
): void {
  const paragraphs = formatAnswerParagraphs(text, { omitTables })
  paragraphs.forEach((paragraph, index) => {
    drawBodyText(
      pdf,
      cursor,
      paragraph,
      {
        fontSize: emphasisFirst && index === 0 ? 11 : 10,
        bold: emphasisFirst && index === 0,
      },
      drawRunningHeader,
    )
  })
}

function drawMetaLine(pdf: jsPDF, cursor: PdfCursor, response: ChatResponse, drawRunningHeader: () => void): void {
  const bits = [
    answerPresentation(response).title,
    response.status,
    response.strategy,
    `${response.data.row_count.toLocaleString('id-ID')} rows`,
  ].filter(Boolean)
  drawBodyText(pdf, cursor, bits.join(' · '), { fontSize: 8, color: MUTED }, drawRunningHeader)
}

function drawDataTable(
  pdf: jsPDF,
  cursor: PdfCursor,
  response: ChatResponse,
  drawRunningHeader: () => void,
): void {
  const { columns, rows } = response.data
  if (!columns.length || !rows.length) return

  const slice = rows.slice(0, MAX_TABLE_ROWS)
  const head = [columns.map(col => formatCellValue(col))]
  const body = slice.map(row => columns.map(col => formatCellValue(row[col])))

  ensureSpace(pdf, cursor, 14, drawRunningHeader)
  drawSectionLabel(pdf, cursor, 'Data table')
  const tableTop = cursor.y

  autoTable(pdf, {
    startY: tableTop,
    margin: { left: MARGIN_MM, right: MARGIN_MM },
    tableWidth: CONTENT_WIDTH_MM,
    head,
    body,
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 8,
      cellPadding: 2.2,
      textColor: SLATE,
      lineColor: LINE,
      lineWidth: 0.15,
      overflow: 'linebreak',
    },
    headStyles: {
      fillColor: INK,
      textColor: [255, 255, 255],
      fontStyle: 'bold',
      fontSize: 8,
    },
    alternateRowStyles: { fillColor: [248, 250, 252] },
  })

  const finalY = (pdf as JsPdfWithAutoTable).lastAutoTable?.finalY ?? tableTop
  cursor.y = finalY + 4

  if (rows.length > MAX_TABLE_ROWS) {
    drawBodyText(
      pdf,
      cursor,
      `Showing first ${MAX_TABLE_ROWS} of ${rows.length.toLocaleString('id-ID')} rows.`,
      { fontSize: 8, color: MUTED },
      drawRunningHeader,
    )
  }
}

function drawKpi(pdf: jsPDF, cursor: PdfCursor, response: ChatResponse, drawRunningHeader: () => void): void {
  const spec = response.chart_spec
  if (!spec || spec.type !== 'kpi') return
  const field = spec.y || response.data.columns[0]
  const raw = field ? response.data.rows[0]?.[field] : undefined
  ensureSpace(pdf, cursor, 12, drawRunningHeader)
  drawSectionLabel(pdf, cursor, 'Key metric')
  drawBodyText(pdf, cursor, `${spec.title}: ${formatCellValue(raw)}`, { bold: true, fontSize: 11 }, drawRunningHeader)
}

async function drawChartSnapshot(
  pdf: jsPDF,
  cursor: PdfCursor,
  node: HTMLElement,
  drawRunningHeader: () => void,
): Promise<void> {
  const { default: html2canvas } = await import('html2canvas')
  const canvas = await html2canvas(node, {
    scale: 2,
    backgroundColor: '#ffffff',
    useCORS: true,
    logging: false,
    width: CHART_CAPTURE_WIDTH_PX,
    windowWidth: CHART_CAPTURE_WIDTH_PX,
  })
  const imgData = canvas.toDataURL('image/png')
  const imgWidthMm = CONTENT_WIDTH_MM
  const imgHeightMm = (canvas.height * imgWidthMm) / canvas.width
  ensureSpace(pdf, cursor, imgHeightMm + 8, drawRunningHeader)
  drawSectionLabel(pdf, cursor, 'Chart')
  pdf.addImage(imgData, 'PNG', MARGIN_MM, cursor.y, imgWidthMm, imgHeightMm)
  cursor.y += imgHeightMm + 6
}

function drawAssistantTurn(
  pdf: jsPDF,
  cursor: PdfCursor,
  response: ChatResponse,
  fallbackText: string,
  turnIndex: number,
  drawRunningHeader: () => void,
  chartNode?: HTMLElement | null,
): Promise<void> {
  ensureSpace(pdf, cursor, 20, drawRunningHeader)
  drawSectionLabel(pdf, cursor, `Answer ${turnIndex}`)
  drawMetaLine(pdf, cursor, response, drawRunningHeader)

  const omitTables = response.data.rows.length > 0
  const narrative = response.answer.direct_answer.trim() || fallbackText.trim()
  drawProseBlocks(pdf, cursor, narrative, omitTables, drawRunningHeader, true)

  if (
    response.answer.executive_summary.trim() &&
    response.answer.executive_summary.trim() !== response.answer.direct_answer.trim()
  ) {
    drawSectionLabel(pdf, cursor, 'Summary')
    drawProseBlocks(pdf, cursor, response.answer.executive_summary, omitTables, drawRunningHeader)
  }

  if (response.answer.insights.length) {
    drawSectionLabel(pdf, cursor, 'Insights')
    drawBulletList(pdf, cursor, response.answer.insights, drawRunningHeader)
  }

  if (response.answer.business_implications.length) {
    drawSectionLabel(pdf, cursor, 'Business implications')
    drawBulletList(pdf, cursor, response.answer.business_implications, drawRunningHeader)
  }

  drawKpi(pdf, cursor, response, drawRunningHeader)

  const visualTypes = ['bar', 'line', 'area', 'scatter', 'pie']
  const hasVisualChart = Boolean(
    response.chart_spec &&
      visualTypes.includes(response.chart_spec.type) &&
      response.chart_spec.x &&
      response.chart_spec.y &&
      response.data.rows.length > 0,
  )

  if (hasVisualChart && chartNode) {
    return drawChartSnapshot(pdf, cursor, chartNode, drawRunningHeader).then(() => {
      drawDataTable(pdf, cursor, response, drawRunningHeader)
      if (response.answer.caveats.length) {
        drawSectionLabel(pdf, cursor, 'Data notes')
        drawBulletList(pdf, cursor, response.answer.caveats, drawRunningHeader)
      }
      cursor.y += 4
    })
  }

  drawDataTable(pdf, cursor, response, drawRunningHeader)
  if (response.answer.caveats.length) {
    drawSectionLabel(pdf, cursor, 'Data notes')
    drawBulletList(pdf, cursor, response.answer.caveats, drawRunningHeader)
  }
  cursor.y += 4
  return Promise.resolve()
}

function assistantChartNode(
  response: ChatResponse,
  chartNodes: HTMLElement[],
  chartNodeIndex: number,
): HTMLElement | null {
  const visualTypes = ['bar', 'line', 'area', 'scatter', 'pie']
  const hasVisualChart = Boolean(
    response.chart_spec &&
      visualTypes.includes(response.chart_spec.type) &&
      response.chart_spec.x &&
      response.chart_spec.y &&
      response.data.rows.length > 0,
  )
  if (!hasVisualChart) return null
  return chartNodes[chartNodeIndex] ?? null
}

export async function downloadConversationPdf(input: ConversationPdfInput): Promise<void> {
  const { title, messages, appName = 'Tempo Scan · Ask Data', chartRoot } = input
  if (!messages.length) return

  const exportedAt = new Date()
  const pdf = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' })
  const cursor: PdfCursor = { y: MARGIN_MM }
  const runningHeader = () => drawDocumentHeader(pdf, cursor, title, appName, exportedAt, true)

  drawDocumentHeader(pdf, cursor, title, appName, exportedAt)

  const chartNodes = chartRoot ? [...chartRoot.querySelectorAll<HTMLElement>('[data-pdf-export-chart]')] : []
  let chartNodeIndex = 0

  let turnIndex = 0
  for (const message of messages) {
    if (message.role === 'user') {
      turnIndex += 1
      drawUserTurn(pdf, cursor, message.content, turnIndex, runningHeader)
      continue
    }

    if (message.response) {
      const chartNode = assistantChartNode(message.response, chartNodes, chartNodeIndex)
      if (chartNode) chartNodeIndex += 1
      await drawAssistantTurn(
        pdf,
        cursor,
        message.response,
        message.content,
        turnIndex || 1,
        runningHeader,
        chartNode,
      )
    } else {
      ensureSpace(pdf, cursor, 12, runningHeader)
      drawSectionLabel(pdf, cursor, `Answer ${turnIndex || 1}`)
      drawBodyText(pdf, cursor, message.content, {}, runningHeader)
      cursor.y += 4
    }
  }

  drawPageFooters(pdf, appName)
  pdf.save(conversationPdfFilename(title))
}
