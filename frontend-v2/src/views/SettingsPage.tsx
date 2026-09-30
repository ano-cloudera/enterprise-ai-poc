'use client'

import { Bot } from 'lucide-react'
import { useModelSelection } from '../lib/modelSelection'


export function SettingsPage() {
  const { models, selection, loading, error, select } = useModelSelection()
  const current = selection ? `${selection.provider}::${selection.model}` : ''
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="page-title">Settings</h1>
      <p className="page-subtitle">Choose one of the models configured and allowed by Backend V2.</p>
      <section className="card-pad mt-5">
        <div className="flex gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-orange-50 text-cloudera-orange"><Bot size={19} /></div><div className="min-w-0 flex-1"><div className="text-sm font-extrabold text-cloudera-navy">AI Model</div><p className="mt-1 text-xs text-slate-400">Unavailable providers remain visible with a safe configuration reason.</p>
          {error && <div className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
          <label className="mt-4 block text-xs font-bold text-slate-600" htmlFor="active-model">Active model</label>
          <select id="active-model" aria-label="Active model" disabled={loading || !models.some(model => model.available)} className="input mt-2" value={current} onChange={event => { const [provider, ...rest] = event.target.value.split('::'); select({ provider: provider as any, model: rest.join('::') }) }}>
            {!current && <option value="">No model available</option>}
            {models.map(model => <option key={`${model.provider}:${model.id}`} value={`${model.provider}::${model.id}`} disabled={!model.available}>{model.label}{model.available ? '' : ` — ${model.reason}`}</option>)}
          </select>
        </div></div>
      </section>
    </div>
  )
}
