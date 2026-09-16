'use client'

import { FormEvent, useEffect, useState } from 'react'
import { Bot, CheckCircle2, Database, Globe2, Save, ShieldCheck, SlidersHorizontal } from 'lucide-react'
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
      <div className="mb-5"><h1 className="page-title">Settings</h1><p className="page-subtitle">Configure the application profile without exposing infrastructure secrets to end users.</p></div>
      {error && <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
      {!settings ? <div className="card-pad text-sm text-slate-500">Loading settings…</div> : (
        <form onSubmit={save} className="space-y-4">
          <SettingSection icon={Bot} title="AI Model Selection" subtitle="Model endpoint is managed by infrastructure; the application uses a provider-agnostic client.">
            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px]"><div><label className="text-xs font-bold text-slate-600">Model name</label><input className="input mt-2" value={settings.model_name} onChange={e => setSettings({ ...settings, model_name: e.target.value })} /></div><div><label className="text-xs font-bold text-slate-600">Runtime mode</label><div className="mt-2 flex h-[42px] items-center rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-bold text-cloudera-navy">{settings.llm_mode}</div></div></div>
            <div className="mt-3 flex items-center gap-2 text-xs text-slate-500"><CheckCircle2 size={14} className="text-emerald-500" />Current proven serving baseline: Qwen3.8-27B-AWQ via vLLM 0.29.0.</div>
          </SettingSection>

          <SettingSection icon={Globe2} title="Response Language" subtitle="Choose the default response language. Auto follows the user's language.">
            <div className="flex flex-wrap gap-3">{['auto','id','en'].map(lang => <button key={lang} type="button" onClick={() => setSettings({ ...settings, language: lang })} className={`rounded-xl border px-4 py-2.5 text-sm font-bold ${settings.language === lang ? 'border-cloudera-orange bg-orange-50 text-cloudera-orange' : 'border-slate-200 bg-white text-slate-600'}`}>{lang === 'auto' ? 'Auto detect' : lang === 'id' ? 'Bahasa Indonesia' : 'English'}</button>)}</div>
          </SettingSection>

          <SettingSection icon={SlidersHorizontal} title="General Prompt / System Instruction" subtitle="Project-specific behavior. Keep security and SQL policies in backend code, not in this prompt.">
            <textarea className="input min-h-[190px] resize-y leading-6" value={settings.system_prompt} onChange={e => setSettings({ ...settings, system_prompt: e.target.value })} />
          </SettingSection>

          <div className="grid gap-4 md:grid-cols-2">
            <SettingSection icon={Database} title="Data Connection" subtitle="Configured by environment variables for local or Cloudera deployment.">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="eyebrow">Active backend</div><div className="mt-2 text-lg font-black text-cloudera-navy">{settings.data_backend}</div><div className="mt-1 text-xs leading-5 text-slate-500">Use DuckDB locally. Trino/CDW is planned for Milestone 5 without changing the frontend contract.</div></div>
            </SettingSection>
            <SettingSection icon={ShieldCheck} title="Guardrails" subtitle="Deterministic policies are always on; Guardrails AI can be layered in via optional dependency/token.">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="eyebrow">Protection mode</div><div className="mt-2 text-lg font-black text-cloudera-navy">{settings.guardrails}</div><div className="mt-1 text-xs leading-5 text-slate-500">Prompt injection checks, read-only SQL, allowlist, row limits, reasoning leakage checks.</div></div>
            </SettingSection>
          </div>

          <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-card"><div className="text-xs text-slate-500">Runtime settings are PoC-level and reset when the backend restarts.</div><button className="btn-primary"><Save size={16} />{saved ? 'Saved' : 'Save Configuration'}</button></div>
        </form>
      )}
    </div>
  )
}

function SettingSection({ icon: Icon, title, subtitle, children }: any) { return <section className="card-pad"><div className="flex gap-3"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-orange-50 text-cloudera-orange"><Icon size={19} /></div><div className="min-w-0 flex-1"><div className="text-sm font-extrabold text-cloudera-navy">{title}</div><p className="mt-1 text-xs leading-5 text-slate-400">{subtitle}</p><div className="mt-4">{children}</div></div></div></section> }
