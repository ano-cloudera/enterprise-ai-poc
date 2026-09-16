'use client'

import { Activity, BadgeCheck, Clock3, Gauge, MessageSquareText, ShieldAlert } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard } from '../components/ChartCard'
import { PageIntro } from '../components/PageIntro'
import { useFetch } from '../hooks/useFetch'
import { api } from '../lib/api'

export function MonitoringPage() {
  const { data, loading, error } = useFetch(api.monitoring)
  if (loading) return <div className="card-pad text-sm text-slate-500">Loading telemetry…</div>
  if (error || !data) return <div className="card-pad border-rose-200 bg-rose-50 text-sm text-rose-700">{error || 'Monitoring unavailable'}</div>
  const cards = [
    { label: 'Total Queries', value: data.total_queries.toLocaleString(), sub: 'captured by telemetry store', icon: MessageSquareText },
    { label: 'Avg. Response Time', value: `${(data.avg_response_time_ms / 1000).toFixed(2)}s`, sub: 'end-to-end workflow', icon: Clock3 },
    { label: 'Success Rate', value: `${data.success_rate.toFixed(1)}%`, sub: 'ok + controlled fallback', icon: BadgeCheck },
    { label: 'SQL Reject Rate', value: `${data.validation_reject_rate.toFixed(1)}%`, sub: 'blocked by validator', icon: ShieldAlert },
  ]
  return (
    <div>
      <PageIntro
        title="AI Monitoring"
        subtitle="Track workflow performance, validation outcomes, and operational health without pretending PoC telemetry is production observability."
      />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(({ label,value,sub,icon:Icon }) => <div key={label} className="card-pad"><div className="flex items-center justify-between"><div className="grid h-9 w-9 place-items-center rounded-xl bg-orange-50 text-cloudera-orange"><Icon size={18} /></div><span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">LIVE</span></div><div className="mt-5 text-xs font-bold text-slate-500">{label}</div><div className="mt-1 text-[26px] font-black text-cloudera-navy">{value}</div><div className="mt-1 text-[11px] text-slate-400">{sub}</div></div>)}</div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(300px,.8fr)]">
        <ChartCard title="Usage Trend" subtitle="AI workflow requests by day">
          <div className="h-[300px]"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.usage_trend} margin={{ top: 10, right: 12, left: -22, bottom: 0 }}><CartesianGrid vertical={false} /><XAxis dataKey="date" tick={{ fontSize: 11, fill: '#8A8EA3' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 11, fill: '#8A8EA3' }} axisLine={false} tickLine={false} /><Tooltip /><Line type="monotone" dataKey="queries" stroke="#FF5A1F" strokeWidth={3} dot={{ fill:'#FF5A1F', r:3, strokeWidth:0 }} /></LineChart></ResponsiveContainer></div>
        </ChartCard>
        <section className="card-pad"><div className="flex items-center gap-2"><Gauge size={17} className="text-cloudera-orange" /><div className="text-sm font-extrabold text-cloudera-navy">System Status</div></div><p className="mt-1 text-xs text-slate-400">Foundation service checks</p><div className="mt-4 space-y-2">{['API Service','Semantic Layer','SQL Validator','Telemetry Store','Model Connector'].map((item,i) => <div key={item} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-3 py-3"><div className="flex items-center gap-2 text-xs font-bold text-slate-700"><span className="h-2 w-2 rounded-full bg-emerald-500" />{item}</div><span className="text-[10px] font-bold text-emerald-600">Operational</span></div>)}</div><div className="mt-4 rounded-xl border border-violet-100 bg-violet-50 p-3 text-[11px] leading-5 text-violet-700">Quality evaluation such as grounded-answer score and hallucination risk is intentionally deferred until golden questions and ground truth are locked.</div></section>
      </div>
      <div className="mt-4 card overflow-hidden"><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><div className="text-sm font-extrabold text-cloudera-navy">Recent Activity</div><div className="mt-1 text-xs text-slate-400">Latest assistant interactions</div></div><div className="chip"><Activity size={13} />SQLite telemetry</div></div><div className="overflow-x-auto"><table className="min-w-full text-left text-xs"><thead className="bg-slate-50 text-slate-400"><tr><th className="px-5 py-3">Time</th><th className="px-5 py-3">Query</th><th className="px-5 py-3">Intent</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Latency</th></tr></thead><tbody>{data.recent_activity.map((row:any,i:number) => <tr key={i} className="border-t border-slate-100"><td className="whitespace-nowrap px-5 py-3 text-slate-500">{new Date(row.timestamp).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })}</td><td className="max-w-xl px-5 py-3 font-semibold text-slate-700">{row.question}</td><td className="px-5 py-3"><span className="rounded-full bg-violet-50 px-2 py-1 text-[10px] font-bold text-violet-700">{row.intent}</span></td><td className="px-5 py-3"><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${row.status === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{row.status}</span></td><td className="px-5 py-3 text-right font-bold text-slate-600">{row.latency_ms} ms</td></tr>)}</tbody></table></div></div>
    </div>
  )
}
