import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppShell } from './AppShell'

vi.mock('next/navigation', () => ({ usePathname: () => '/' }))
vi.mock('../lib/project', () => ({
  useProject: () => ({ config: { project_name: 'Tempo Scan Commercial Intelligence Assistant' } }),
}))

describe('Dashboard shell navigation', () => {
  afterEach(() => { cleanup(); vi.useRealTimers() })
  it('removes internal foundation cards and exposes the customer navigation', () => {
    render(<AppShell><div>Dashboard content</div></AppShell>)
    for (const label of ['Dashboard', 'Ask AI', 'Market Intelligence', 'AI Monitoring', 'Settings']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
    expect(screen.queryByText('Active Project')).toBeNull()
    expect(screen.queryByText('Foundation readiness 88%')).toBeNull()
    expect(screen.getAllByText('Powered by Cloudera AI').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Commercial Intelligence')).toHaveLength(2)
  })

  it('opens and closes responsive navigation from the menu button', () => {
    render(<AppShell><div>Dashboard content</div></AppShell>)
    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    screen.getByRole('dialog', { name: 'Main navigation' })
    fireEvent.click(screen.getByRole('button', { name: 'Close navigation' }))
    expect(screen.queryByRole('dialog', { name: 'Main navigation' })).toBeNull()
  })

  it('uses a prominent application header hierarchy', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-16T04:45:00.000Z'))
    render(<AppShell><div>Dashboard content</div></AppShell>)
    const header = screen.getByRole('banner')

    expect(header.className).toContain('h-20')
    expect(header.className).toContain('sm:h-[88px]')
    expect(within(header).getByText('Commercial Intelligence').className).toContain('text-xl')
    expect(within(header).getByText('Commercial Intelligence').className).toContain('sm:text-[22px]')
    expect(within(header).getAllByText('Tempo Scan')[0].className).toContain('sm:text-sm')
    const latestOpened = within(header).getByText('Latest opened')
    within(header).getByText('16 Sep 2026, 11:45 WIB')
    expect(latestOpened.parentElement?.className).toContain('text-left')
    expect(latestOpened.parentElement?.parentElement?.className).toContain('border-r')
    expect(within(header).queryByText('Governed commercial workspace')).toBeNull()
  })
})
