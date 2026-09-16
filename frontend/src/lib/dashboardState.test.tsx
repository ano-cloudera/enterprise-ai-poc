import React from 'react'
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { DashboardStateProvider, useDashboardState } from './dashboardState'

function Harness() {
  const store = useDashboardState()
  return <>
    <output aria-label="region">{store.state.filters.region.join(',')}</output>
    <output aria-label="previous">{store.previousDashboardState?.filters.region.join(',') || 'none'}</output>
    <output aria-label="actions">{store.aiAppliedActions.length}</output>
    <button onClick={() => store.applyDashboardAiActions([
      { type: 'SET_FILTER', target: 'region', value: ['Jawa Barat'] },
      { type: 'SET_DATE_RANGE', value: 'current_month' },
    ])}>Apply AI</button>
    <button onClick={store.undoAiChanges}>Undo AI</button>
    <button onClick={store.reset}>Reset all</button>
  </>
}

describe('shared dashboard AI transaction state', () => {
  afterEach(cleanup)
  it('captures one previous state and restores it on undo', () => {
    render(<DashboardStateProvider><Harness /></DashboardStateProvider>)

    act(() => screen.getByRole('button', { name: 'Apply AI' }).click())
    expect(screen.getByLabelText('region').textContent).toBe('Jawa Barat')
    expect(screen.getByLabelText('previous').textContent).toBe('none')
    expect(screen.getByLabelText('actions').textContent).toBe('2')

    act(() => screen.getByRole('button', { name: 'Undo AI' }).click())
    expect(screen.getByLabelText('region').textContent).toBe('')
    expect(screen.getByLabelText('actions').textContent).toBe('0')
  })

  it('reset clears current context and AI transaction history', () => {
    render(<DashboardStateProvider><Harness /></DashboardStateProvider>)
    act(() => screen.getByRole('button', { name: 'Apply AI' }).click())
    act(() => screen.getByRole('button', { name: 'Reset all' }).click())

    expect(screen.getByLabelText('region').textContent).toBe('')
    expect(screen.getByLabelText('actions').textContent).toBe('0')
  })
})
