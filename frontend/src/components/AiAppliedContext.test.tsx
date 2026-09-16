import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AiAppliedContext } from './AiAppliedContext'

describe('AI applied context indicator', () => {
  afterEach(cleanup)
  it('renders active context and removes it through one callback', () => {
    const onRemove = vi.fn()
    render(<AiAppliedContext items={[{ kind: 'filter', target: 'region', label: 'Jawa Barat' }]} onRemove={onRemove} onReset={vi.fn()} />)
    screen.getByText('Applied by AI:')
    screen.getByText('Jawa Barat')
    screen.getByRole('button', { name: 'Remove Jawa Barat' }).click()
    expect(onRemove).toHaveBeenCalledWith('filter', 'region')
  })

  it('offers undo separately from reset when an AI transaction exists', () => {
    const onUndo = vi.fn()
    const onReset = vi.fn()
    render(<AiAppliedContext items={[{ kind: 'filter', target: 'region', label: 'Jawa Barat' }]} onRemove={vi.fn()} onReset={onReset} onUndo={onUndo} canUndo />)

    screen.getByRole('button', { name: 'Undo AI changes' }).click()
    screen.getByRole('button', { name: 'Reset all' }).click()
    expect(onUndo).toHaveBeenCalledOnce()
    expect(onReset).toHaveBeenCalledOnce()
  })
})
