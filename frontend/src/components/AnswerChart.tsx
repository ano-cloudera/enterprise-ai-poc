import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell, Legend } from 'recharts'
import type { TooltipValueType } from 'recharts'
import type { ChartSpec } from '../types/api'
import { formatBusinessLabel, formatBusinessValue } from '../lib/businessPresentation'

export function AnswerChart({ chart }: { chart: ChartSpec | null }) {
  if (!chart || chart.type === 'none' || chart.type === 'table') return null
  const rows = chart.x.map((x, index) => ({ x, ...(Object.fromEntries(chart.series.map(series => [series.name, Number(series.data[index] ?? 0)]))) }))
  const formatValue = (value: number) => formatBusinessValue(chart.metric || chart.y_label || 'value', value, chart.metric || undefined)
  const tooltipFormatter = (value: TooltipValueType | undefined, name: number | string | undefined) => {
    const displayValue = Array.isArray(value) ? value[0] : value
    return [formatValue(Number(displayValue ?? 0)), formatBusinessLabel(String(name ?? 'Value'))] as [string, string]
  }
  return (
    <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
      <div className="mb-3 text-xs font-extrabold text-cloudera-navy">{chart.title}</div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          {chart.type === 'bar' ? (
            <BarChart data={rows}><CartesianGrid vertical={false} /><XAxis dataKey="x" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} tickFormatter={formatValue} /><Tooltip formatter={tooltipFormatter} />{chart.series.map((s, i) => <Bar key={s.name} dataKey={s.name} name={formatBusinessLabel(s.name)} fill={i === 0 ? '#FF5A1F' : '#635BFF'} radius={[5,5,0,0]} />)}</BarChart>
          ) : chart.type === 'area' ? (
            <AreaChart data={rows}><CartesianGrid vertical={false} /><XAxis dataKey="x" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} tickFormatter={formatValue} /><Tooltip formatter={tooltipFormatter} />{chart.series.map((s, i) => <Area key={s.name} type="monotone" dataKey={s.name} name={formatBusinessLabel(s.name)} stroke={i === 0 ? '#FF5A1F' : '#635BFF'} fill={i === 0 ? '#FF5A1F22' : '#635BFF22'} />)}</AreaChart>
          ) : chart.type === 'pie' ? (
            <PieChart><Pie data={rows} dataKey={chart.series[0]?.name} nameKey="x" innerRadius={42} outerRadius={76}>{rows.map((_, i) => <Cell key={i} fill={['#FF5A1F','#635BFF','#3EBAA5','#9A8CFF'][i % 4]} />)}</Pie><Tooltip formatter={tooltipFormatter} /><Legend /></PieChart>
          ) : (
            <LineChart data={rows}><CartesianGrid vertical={false} /><XAxis dataKey="x" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} tickFormatter={formatValue} /><Tooltip formatter={tooltipFormatter} />{chart.series.map((s, i) => <Line key={s.name} type="monotone" dataKey={s.name} name={formatBusinessLabel(s.name)} stroke={i === 0 ? '#FF5A1F' : '#635BFF'} strokeWidth={2.5} dot={{ r: 3 }} />)}</LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
