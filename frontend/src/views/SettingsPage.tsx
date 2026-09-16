'use client'

import { FormEvent, useEffect, useState } from 'react'
import { Bot, Globe2, Save, SlidersHorizontal } from 'lucide-react'
import { api } from '../lib/api'

export function SettingsPage() {
  const [settings, setSettings] = useState<any>(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { api.settings().then(setSettings).catch((e: Error) => setError(e.message)) }, [])

  async function save(e: FormEvent) {
    e.preventDefault(); setSaved(false)
    try { const updated = await api.updateSettings({ language: settings.language, system_prompt: settings.system_prompt, model_name: settings.model_name }); setSettings(updated); setSaved(true); setTimeout(() => setSaved(false), 1800) }
    catch (err) { setError((err as Error).message) }
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-5"><h1 className="page-title">Settings</h1><p className="page-subtitle">Configure how Tempo Scan AI responds for your team.</p></div>
      {error && <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
      {!settings ? <div className="card-pad text-sm text-slate-500">Loading settings…</div> : (
        <form onSubmit={save} className="space-y-4">
          <SettingSection icon={Bot} title="AI Model">
            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px]"><div><label className="text-xs font-bold text-slate-600">Active model</label><input className="input mt-2" value={settings.model_name} onChange={e => setSettings({ ...settings, model_name: e.target.value })} /></div><div><label className="text-xs font-bold text-slate-600">Runtime</label><div className="mt-2 flex h-[42px] items-center rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-bold text-cloudera-navy">{formatRuntimeMode(settings.llm_mode)}</div></div></div>
          </SettingSection>

          <SettingSection icon={Globe2} title="Response Language" subtitle="Choose the default response language. Auto follows the user's language.">
            <div className="flex flex-wrap gap-3">{['auto','id','en'].map(lang => <button key={lang} type="button" onClick={() => setSettings({ ...settings, language: lang })} className={`rounded-xl border px-4 py-2.5 text-sm font-bold ${settings.language === lang ? 'border-cloudera-orange bg-orange-50 text-cloudera-orange' : 'border-slate-200 bg-white text-slate-600'}`}>{lang === 'auto' ? 'Auto detect' : lang === 'id' ? 'Bahasa Indonesia' : 'English'}</button>)}</div>
          </SettingSection>

          <SettingSection icon={SlidersHorizontal} title="General Prompt / System Instruction" subtitle="Guide how the assistant should behave for your team.">
            <textarea className="input min-h-[190px] resize-y leading-6" value={settings.system_prompt} onChange={e => setSettings({ ...settings, system_prompt: e.target.value })} />
          </SettingSection>

          <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-card"><div className="text-xs text-slate-500">Changes apply to this workspace.</div><button className="btn-primary"><Save size={16} />{saved ? 'Saved' : 'Save Configuration'}</button></div>
        </form>
      )}
    </div>
  )
}

function formatRuntimeMode(mode: string) {
  const normalized = String(mode || '').toLowerCase()
  if (normalized === 'live' || normalized === 'production') return 'Connected'
  if (normalized === 'mock') return 'Mock'
  return mode ? 'Configured' : 'Not configured'
}

function SettingSection({ icon: Icon, title, subtitle, children }: any) { return <section className="card-pad"><div className="flex gap-3"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-orange-50 text-cloudera-orange"><Icon size={19} /></div><div className="min-w-0 flex-1"><div className="text-sm font-extrabold text-cloudera-navy">{title}</div>{subtitle && <p className="mt-1 text-xs leading-5 text-slate-400">{subtitle}</p>}<div className="mt-4">{children}</div></div></div></section> }
