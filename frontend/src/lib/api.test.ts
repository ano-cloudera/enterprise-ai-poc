import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './api'
import type { DashboardState } from '../types/api'

const dashboardState: DashboardState = {
  filters: {},
  date_range: { preset: null, start: null, end: null },
  metric: 'x', dimension: 'y', highlights: [], ai_applied_context: [], revision: 1,
  chat: { chart: null, table: { visible: false, columns: [] } },
}

function chatResponsePayload() {
  return {
    status: 'ok', question: 'Berapa Gross Sales Q4 2024?',
    answer: { summary: 'Rp 3.8T', drivers: [], recommended_actions: [], caveats: [] },
    data: { columns: [], rows: [] },
    chart_spec: null,
    ui_actions: [],
    metadata: {
      trace_id: 't1', session_id: 's1', intent: 'agent_studio',
      resolved_context: dashboardState,
      execution_time_ms: 1,
    },
  }
}

// Builds a fetch() Response whose body streams the given raw SSE text
// across the given chunks — e.g. [['data: {...json...}\n\n']] delivers
// everything in a single reader.read() call, mirroring what was actually
// observed against Cloudera AI: the terminal {"type": "done"} frame
// arriving in the same read() that also reports done: true.
function sseResponse(chunks: string[]) {
  const encoder = new TextEncoder()
  let index = 0
  const body = {
    getReader: () => ({
      read: async () => {
        if (index >= chunks.length) return { done: true, value: undefined }
        const value = encoder.encode(chunks[index])
        index += 1
        const isLast = index >= chunks.length
        return { done: isLast, value }
      },
    }),
  }
  return { ok: true, body } as unknown as Response
}

describe('api.chatStream', () => {
  afterEach(() => vi.restoreAllMocks())

  it('yields the terminal done frame even when it arrives in the same read() that reports done: true', async () => {
    const payload = chatResponsePayload()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      sseResponse([`data: ${JSON.stringify({ type: 'progress', label: 'Memahami pertanyaan kamu...' })}\n\ndata: ${JSON.stringify({ type: 'done', response: payload })}\n\n`]),
    ))

    const events = []
    for await (const event of api.chatStream('Berapa Gross Sales Q4 2024?', 's1', dashboardState)) {
      events.push(event)
    }

    expect(events).toHaveLength(2)
    expect(events[0]).toEqual({ type: 'progress', label: 'Memahami pertanyaan kamu...' })
    expect(events[1].type).toBe('done')
    expect((events[1] as { type: 'done'; response: { answer: { summary: string } } }).response.answer.summary).toBe('Rp 3.8T')
  })

  it('yields progress and done frames split across multiple network chunks', async () => {
    const payload = chatResponsePayload()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      sseResponse([
        `data: ${JSON.stringify({ type: 'progress', label: 'Memahami pertanyaan kamu...' })}\n\n`,
        ': keep-alive\n\n',
        `data: ${JSON.stringify({ type: 'progress', label: 'Mengambil angka dari data governed...' })}\n\n`,
        `data: ${JSON.stringify({ type: 'done', response: payload })}\n\n`,
      ]),
    ))

    const events = []
    for await (const event of api.chatStream('Berapa Gross Sales Q4 2024?', 's1', dashboardState)) {
      events.push(event)
    }

    expect(events.map(e => e.type)).toEqual(['progress', 'progress', 'done'])
  })
})
