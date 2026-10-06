import type { ChatResponse } from '../types/api'

export type ClarificationChoice = {
  id: string
  label: string
  /** Short reply merged with prior question on the backend (contextualize_question). */
  submitText: string
}

function combinedAnswerText(response: ChatResponse): string {
  const parts = [
    response.answer.direct_answer,
    response.answer.executive_summary,
    ...(response.answer.insights ?? []),
  ]
  return parts.filter(Boolean).join(' ').toLowerCase().replace(/–/g, '-')
}

/** Quick-reply chips when the assistant asks a known governed clarification. */
export function clarificationChoices(response: ChatResponse): ClarificationChoice[] | null {
  if (response.status !== 'CLARIFICATION' && response.strategy !== 'clarification') return null
  const text = combinedAnswerText(response)

  if (text.includes('sell-in') && text.includes('sell-out')) {
    return [
      {
        id: 'sell-in',
        label: 'Sell-In (Tempo → customer)',
        submitText: 'Sell-In (penjualan Tempo ke customer)',
      },
      {
        id: 'sell-out',
        label: 'Sell-Out (partner → konsumen)',
        submitText: 'Sell-Out (penjualan partner ke konsumen)',
      },
    ]
  }

  if (
    (text.includes('stok dc') && text.includes('stok store')) ||
    (text.includes('dc partner') && text.includes('store retail'))
  ) {
    return [
      { id: 'wh', label: 'Stok gudang Tempo', submitText: 'Stok gudang Tempo' },
      { id: 'dc', label: 'Stok DC partner', submitText: 'Stok DC partner Alfamart' },
      { id: 'store', label: 'Stok toko retail', submitText: 'Stok toko retail Alfamart' },
    ]
  }

  if (text.includes('sell-out') && text.includes('sell-in') && text.includes('rasio')) {
    return [
      { id: 'so_si', label: 'Sell-Out / Sell-In', submitText: 'Sell-Out dibagi Sell-In' },
      { id: 'si_so', label: 'Sell-In / Sell-Out', submitText: 'Sell-In dibagi Sell-Out' },
    ]
  }

  if (text.includes('picking') && text.includes('unloading')) {
    return [
      {
        id: 'picking',
        label: 'Durasi picking',
        submitText: 'Analisa durasi picking per sales office Q4 2024',
      },
      {
        id: 'unloading',
        label: 'Durasi unloading',
        submitText: 'Analisa durasi unloading per sales office Q4 2024',
      },
    ]
  }

  return null
}
