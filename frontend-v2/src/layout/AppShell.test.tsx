import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppShell } from './AppShell'

vi.mock('next/navigation', () => ({ usePathname: () => '/' }))

describe('V2 application shell', () => {
  afterEach(cleanup)

  it('exposes Ask Data and Settings without Dashboard or Monitoring', () => {
    render(<AppShell><div>Ask Data content</div></AppShell>)

    expect(screen.getAllByText('Ask Data').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Settings').length).toBeGreaterThan(0)
    expect(screen.queryByText('Dashboard')).toBeNull()
    expect(screen.queryByText('AI Monitoring')).toBeNull()
    screen.getByText('Ask Data content')
  })
})
