import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('recharts', () => {
  const container = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  return {
    ResponsiveContainer: container, ScatterChart: container, BarChart: container, AreaChart: container,
    LineChart: container, PieChart: container, CartesianGrid: () => null, Tooltip: () => null,
    Legend: () => <div data-testid="legend" />, Cell: () => null, Pie: container,
    XAxis: ({ dataKey }: { dataKey?: string }) => <div data-testid="x-axis" data-key={dataKey} />,
    YAxis: ({ dataKey }: { dataKey?: string }) => <div data-testid="y-axis" data-key={dataKey} />,
    Scatter: ({ name }: { name?: string }) => <div data-testid="scatter" data-name={name} />,
    Bar: () => null, Area: () => null, Line: () => null,
  }
})

import { AnswerChart } from './AnswerChart'

describe('AnswerChart', () => {
  afterEach(cleanup)

  it('binds both numeric scatter axes and renders declared series', () => {
    render(<AnswerChart chart={{ type: 'scatter', title: 'Stock vs sales', x: 'stock', y: 'sales', series: 'region' }} rows={[
      { stock: 10, sales: 20, region: 'West' },
      { stock: 12, sales: 24, region: 'East' },
    ]} />)

    expect(screen.getByTestId('x-axis').getAttribute('data-key')).toBe('stock')
    expect(screen.getByTestId('y-axis').getAttribute('data-key')).toBe('sales')
    expect(screen.getAllByTestId('scatter')).toHaveLength(2)
    expect(screen.getByTestId('legend')).toBeTruthy()
  })
})
