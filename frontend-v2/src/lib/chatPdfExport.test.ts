import { describe, expect, it } from 'vitest'

import { conversationPdfFilename } from './chatPdfExport'

describe('chatPdfExport', () => {
  it('builds a safe pdf filename from the session title', () => {
    expect(conversationPdfFilename('Top sell-in Q4?')).toMatch(/^tempo-scan-Top-sell-in-Q4-\d{4}-\d{2}-\d{2}\.pdf$/)
  })
})
