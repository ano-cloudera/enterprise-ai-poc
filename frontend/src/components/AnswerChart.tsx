import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell, Legend } from 'recharts'
import type { TooltipValueType } from 'recharts'
import type { ChartSpec } from '../types/api'
import { formatBusinessLabel, formatBusinessValue } from '../lib/businessPresentation'

const SERIES_COLORS = ['#FF5A1F', '#635BFF', '#3EBAA5', '#9A8CFF']
const AXIS_TICK = { fontSize: 10, fill: '#7C849A' }
const GRID_STROKE = '#E7E8F0'
const legendStyle = { fontSize: 11, paddingTop: 8 }

export function AnswerChart({ chart }: { chart: ChartSpec | null }) {
  if (!chart || chart.type === 'none' || chart.type === 'table') return null
  const rows = chart.x.map((x, index) => ({ x, ...(Object.fromEntries(chart.series.map(series => [series.name, Number(series.data[index] ?? 0)]))) }))
  const formatValue = (value: number) => formatBusinessValue(chart.metric || chart.y_label || 'value', value, chart.metric || undefined, chart.unit_format)
  const tooltipFormatter = (value: TooltipValueType | undefined, name: number | string | undefined) => {
    const displayValue = Array.isArray(value) ? value[0] : value
    return [formatValue(Number(displayValue ?? 0)), formatBusinessLabel(String(name ?? 'Value'))] as [string, string]
  }
  const legendFormatter = (value: string) => <span className="text-slate-600">{formatBusinessLabel(value)}</span>
  const showLegend = chart.series.length >= 2
  return (
    <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
      <div className="mb-3 text-xs font-extrabold text-cloudera-navy">{chart.title}</div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          {chart.type === 'bar' ? (
            <BarChart data={rows} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID_STROKE} />
              <XAxis dataKey="x" tick={AXIS_TICK} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS_TICK} tickFormatter={formatValue} axisLine={false} tickLine={false} width={56} />
              <Tooltip formatter={tooltipFormatter} />
              {showLegend && <Legend formatter={legendFormatter} wrapperStyle={legendStyle} iconSize={8} iconType="circle" />}
              {chart.series.map((s, i) => <Bar key={s.name} dataKey={s.name} name={formatBusinessLabel(s.name)} fill={SERIES_COLORS[i % SERIES_COLORS.length]} radius={[4, 4, 0, 0]} maxBarSize={24} />)}
            </BarChart>
          ) : chart.type === 'area' ? (
            <AreaChart data={rows} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID_STROKE} />
              <XAxis dataKey="x" tick={AXIS_TICK} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS_TICK} tickFormatter={formatValue} axisLine={false} tickLine={false} width={56} />
              <Tooltip formatter={tooltipFormatter} />
              {showLegend && <Legend formatter={legendFormatter} wrapperStyle={legendStyle} iconSize={8} iconType="circle" />}
              {chart.series.map((s, i) => <Area key={s.name} type="monotone" dataKey={s.name} name={formatBusinessLabel(s.name)} stroke={SERIES_COLORS[i % SERIES_COLORS.length]} strokeWidth={2} fill={SERIES_COLORS[i % SERIES_COLORS.length]} fillOpacity={0.1} />)}
            </AreaChart>
          ) : chart.type === 'pie' ? (
            <PieChart>
              <Pie data={rows} dataKey={chart.series[0]?.name} nameKey="x" innerRadius={42} outerRadius={68} paddingAngle={2} stroke="#F7F8FC" strokeWidth={2}>
                {rows.map((_, i) => <Cell key={i} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={tooltipFormatter} />
              <Legend formatter={legendFormatter} wrapperStyle={legendStyle} iconSize={8} iconType="circle" />
            </PieChart>
          ) : (
            <LineChart data={rows} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID_STROKE} />
              <XAxis dataKey="x" tick={AXIS_TICK} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS_TICK} tickFormatter={formatValue} axisLine={false} tickLine={false} width={56} />
              <Tooltip formatter={tooltipFormatter} />
              {showLegend && <Legend formatter={legendFormatter} wrapperStyle={legendStyle} iconSize={8} iconType="circle" />}
              {chart.series.map((s, i) => <Line key={s.name} type="monotone" dataKey={s.name} name={formatBusinessLabel(s.name)} stroke={SERIES_COLORS[i % SERIES_COLORS.length]} strokeWidth={2} dot={{ r: 3, strokeWidth: 0 }} />)}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
