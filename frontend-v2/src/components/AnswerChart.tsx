import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import type { ChartSpec } from '../types/api'

const COLORS = ['#FF5A1F', '#635BFF', '#3EBAA5', '#9A8CFF']
const tick = { fontSize: 12, fill: '#64748B' }

function formatAxisNumber(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(abs % 1_000_000_000 === 0 ? 0 : 1)}B`
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(abs % 1_000_000 === 0 ? 0 : 1)}M`
  if (abs >= 1_000) return `${(value / 1_000).toFixed(abs % 1_000 === 0 ? 0 : 1)}K`
  return String(value)
}

function formatTooltipValue(value: unknown): string {
  return typeof value === 'number' ? value.toLocaleString('id-ID') : String(value ?? '')
}

export function AnswerChart({ chart, rows }: { chart: ChartSpec | null; rows: Record<string, unknown>[] }) {
  if (!chart || chart.type === 'table' || chart.type === 'kpi' || !chart.x || !chart.y || !rows.length) return null
  const seriesNames = chart.series ? [...new Set(rows.map(row => String(row[chart.series!] ?? 'Unknown')))] : []
  const flattenRankingSeries = chart.type === 'bar' && Boolean(chart.series) && rows.length > 1 && seriesNames.length === rows.length
  const xKey = flattenRankingSeries ? '__category' : chart.x
  const visibleSeriesNames = flattenRankingSeries ? [] : seriesNames
  const yField = chart.y!
  const rawYValues = rows.map(row => Number(row[yField] ?? 0))
  const maxY = rawYValues.length ? Math.max(...rawYValues) : 0
  const scaleRatioToPercent =
    chart.type === 'bar' &&
    yField === 'metric_value' &&
    rawYValues.every(value => value >= 0 && value <= 1.5) &&
    (maxY <= 1 || /fill rate|service level|sl\b/i.test(chart.title))
  const toDisplayY = (value: unknown) => {
    const numeric = Number(value ?? 0)
    return scaleRatioToPercent ? numeric * 100 : numeric
  }
  const data = flattenRankingSeries
    ? rows.map(row => ({ ...row, __category: `${String(row[chart.x!] ?? '')} · ${String(row[chart.series!] ?? 'Unknown')}`, [yField]: toDisplayY(row[yField]) }))
    : seriesNames.length
    ? [...rows.reduce((groups, row) => {
        const category = String(row[chart.x!] ?? '')
        const point = groups.get(category) || { [chart.x!]: row[chart.x!] }
        point[String(row[chart.series!] ?? 'Unknown')] = toDisplayY(row[chart.y!])
        groups.set(category, point)
        return groups
      }, new Map<string, Record<string, unknown>>()).values()]
    : rows.map(row => ({ ...row, [yField]: toDisplayY(row[yField]) }))
  const axes = <><CartesianGrid vertical={false} stroke="#E7E8F0" /><XAxis dataKey={xKey} tick={tick} axisLine={false} tickLine={false} minTickGap={24} height={48} /><YAxis tick={tick} axisLine={false} tickLine={false} width={56} tickFormatter={formatAxisNumber} /><Tooltip formatter={formatTooltipValue} />{visibleSeriesNames.length > 0 && <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />}</>
  const keys = visibleSeriesNames.length ? visibleSeriesNames : [yField]
  return <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/60 p-5"><div className="mb-4 text-sm font-extrabold text-cloudera-navy">{chart.title}</div><div className="h-64"><ResponsiveContainer width="100%" height="100%">
    {chart.type === 'bar' ? <BarChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>{axes}{keys.map((key, index) => <Bar key={key} dataKey={key} fill={COLORS[index % COLORS.length]} radius={[6, 6, 0, 0]} maxBarSize={54} />)}</BarChart>
      : chart.type === 'area' ? <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>{axes}{keys.map((key, index) => <Area key={key} dataKey={key} stroke={COLORS[index % COLORS.length]} fill={COLORS[index % COLORS.length]} fillOpacity={0.12} />)}</AreaChart>
      : chart.type === 'scatter' ? <ScatterChart margin={{ top: 8, right: 12, bottom: 8, left: 0 }}><CartesianGrid vertical={false} stroke="#E7E8F0" /><XAxis type="number" dataKey={chart.x} name={chart.x} tick={tick} /><YAxis type="number" dataKey={chart.y} name={chart.y} tick={tick} width={56} tickFormatter={formatAxisNumber} /><Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={formatTooltipValue} />{chart.series ? seriesNames.map((name, index) => <Scatter key={name} name={name} data={rows.filter(row => String(row[chart.series!] ?? 'Unknown') === name)} fill={COLORS[index % COLORS.length]} />) : <Scatter data={data} fill={COLORS[2]} />}{chart.series && <Legend wrapperStyle={{ fontSize: 12 }} />}</ScatterChart>
      : chart.type === 'pie' ? <PieChart><Pie data={data} dataKey={chart.y} nameKey={chart.x} innerRadius={52} outerRadius={88}>{data.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}</Pie><Tooltip formatter={formatTooltipValue} /><Legend wrapperStyle={{ fontSize: 12 }} /></PieChart>
      : <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>{axes}{keys.map((key, index) => <Line key={key} dataKey={key} stroke={COLORS[index % COLORS.length]} strokeWidth={2} />)}</LineChart>}
  </ResponsiveContainer></div></div>
}
