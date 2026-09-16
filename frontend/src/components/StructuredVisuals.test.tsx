import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DataTable } from './DataTable'
import { KpiCard } from './KpiCard'

const Icon = () => <span aria-hidden="true" />

describe('structured visual feedback', () => {
  it('visibly emphasizes a highlighted KPI card', () => {
    const { container } = render(
      <KpiCard label="Top Region" value="Jawa Barat" format="text" delta={null} icon={Icon} highlighted />,
    )

    expect(container.firstElementChild?.className).toContain('ring-2')
  })

  it('renders a safe fallback for absent table data', () => {
    render(<DataTable columns={[]} rows={[]} />)

    expect(screen.getByText('No structured table data is available.')).toBeTruthy()
  })

  it('formats table headers and governed values for business readers', () => {
    render(<DataTable columns={['current_value', 'percentage_change']} rows={[{ current_value: 38501.337000000004, percentage_change: 18.21664440535221 }]} />)
    screen.getByText('Current Value')
    screen.getByText('Percentage Change')
    screen.getByText('Rp38.50B')
    screen.getByText('+18.2%')
  })
})
