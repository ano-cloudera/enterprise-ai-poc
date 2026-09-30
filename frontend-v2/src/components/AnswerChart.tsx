import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import type { ChartSpec } from '../types/api'

const COLORS = ['#FF5A1F', '#635BFF', '#3EBAA5', '#9A8CFF']
const tick = { fontSize: 10, fill: '#7C849A' }

export function AnswerChart({ chart, rows }: { chart: ChartSpec | null; rows: Record<string, unknown>[] }) {
  if (!chart || chart.type === 'table' || chart.type === 'kpi' || !chart.x || !chart.y || !rows.length) return null
  const seriesNames = chart.series ? [...new Set(rows.map(row => String(row[chart.series!] ?? 'Unknown')))] : []
  const data = seriesNames.length
    ? [...rows.reduce((groups, row) => {
        const category = String(row[chart.x!] ?? '')
        const point = groups.get(category) || { [chart.x!]: row[chart.x!] }
        point[String(row[chart.series!] ?? 'Unknown')] = Number(row[chart.y!] ?? 0)
        groups.set(category, point)
        return groups
      }, new Map<string, Record<string, unknown>>()).values()]
    : rows.map(row => ({ ...row, [chart.y!]: Number(row[chart.y!] ?? 0) }))
  const axes = <><CartesianGrid vertical={false} stroke="#E7E8F0" /><XAxis dataKey={chart.x} tick={tick} axisLine={false} tickLine={false} /><YAxis tick={tick} axisLine={false} tickLine={false} width={56} /><Tooltip />{seriesNames.length > 0 && <Legend />}</>
  const keys = seriesNames.length ? seriesNames : [chart.y]
  return <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/60 p-4"><div className="mb-3 text-xs font-extrabold text-cloudera-navy">{chart.title}</div><div className="h-52"><ResponsiveContainer width="100%" height="100%">
    {chart.type === 'bar' ? <BarChart data={data}>{axes}{keys.map((key, index) => <Bar key={key} dataKey={key} fill={COLORS[index % COLORS.length]} radius={[4, 4, 0, 0]} />)}</BarChart>
      : chart.type === 'area' ? <AreaChart data={data}>{axes}{keys.map((key, index) => <Area key={key} dataKey={key} stroke={COLORS[index % COLORS.length]} fill={COLORS[index % COLORS.length]} fillOpacity={0.12} />)}</AreaChart>
      : chart.type === 'scatter' ? <ScatterChart><CartesianGrid vertical={false} stroke="#E7E8F0" /><XAxis type="number" dataKey={chart.x} name={chart.x} tick={tick} /><YAxis type="number" dataKey={chart.y} name={chart.y} tick={tick} width={56} /><Tooltip cursor={{ strokeDasharray: '3 3' }} />{chart.series ? seriesNames.map((name, index) => <Scatter key={name} name={name} data={rows.filter(row => String(row[chart.series!] ?? 'Unknown') === name)} fill={COLORS[index % COLORS.length]} />) : <Scatter data={data} fill={COLORS[2]} />}{chart.series && <Legend />}</ScatterChart>
      : chart.type === 'pie' ? <PieChart><Pie data={data} dataKey={chart.y} nameKey={chart.x} innerRadius={45} outerRadius={75}>{data.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}</Pie><Tooltip /><Legend /></PieChart>
      : <LineChart data={data}>{axes}{keys.map((key, index) => <Line key={key} dataKey={key} stroke={COLORS[index % COLORS.length]} strokeWidth={2} />)}</LineChart>}
  </ResponsiveContainer></div></div>
}
