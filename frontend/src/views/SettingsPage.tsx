'use client'

import { useEffect, useMemo, useState } from 'react'
import { appConfig } from '../config/appConfig'
import { PageCenter } from '../components/PageCenter'
import {
  friendlyUnavailableMessage,
  modelSelectionValue,
  parseModelSelectionValue,
  providerDeploymentHint,
  providerDisplayName,
  uniqueProviders,
} from '../lib/modelLabels'
import { useModelSelection } from '../lib/modelSelection'
import type { ModelInfo } from '../types/api'

function ModelOptions({ models, groupByProvider }: { models: ModelInfo[]; groupByProvider: boolean }) {
  if (!groupByProvider) {
    return models.map(model => (
      <option key={modelSelectionValue(model)} value={modelSelectionValue(model)} disabled={!model.available}>
        {model.label}
      </option>
    ))
  }

  const providers = uniqueProviders(models)
  return providers.map(provider => {
    const group = models.filter(model => model.provider === provider)
    return (
      <optgroup key={provider} label={providerDisplayName(provider)}>
        {group.map(model => (
          <option key={modelSelectionValue(model)} value={modelSelectionValue(model)} disabled={!model.available}>
            {model.label}
          </option>
        ))}
      </optgroup>
    )
  })
}

export function SettingsPage() {
  const { models, selection, loading, error, select, retryLoad } = useModelSelection()
  const [draftValue, setDraftValue] = useState('')

  const hasAvailableModel = models.some(model => model.available)
  const groupByProvider = uniqueProviders(models).length > 1

  const committedValue = selection ? `${selection.provider}::${selection.model}` : ''

  useEffect(() => {
    if (loading) return
    setDraftValue(committedValue)
  }, [loading, committedValue])

  const draftSelection = useMemo(() => parseModelSelectionValue(draftValue), [draftValue])

  const selectedModel = useMemo(
    () =>
      models.find(
        model => model.provider === draftSelection?.provider && model.id === draftSelection?.model,
      ) ?? null,
    [models, draftSelection],
  )

  const draftDirty = Boolean(draftValue && draftValue !== committedValue)
  const canSave =
    draftDirty &&
    draftSelection &&
    models.some(
      model =>
        model.available &&
        model.provider === draftSelection.provider &&
        model.id === draftSelection.model,
    )

  function saveModel() {
    if (!draftSelection || !canSave) return
    select(draftSelection)
  }

  return (
    <PageCenter className="max-w-[760px]">
      <h1 className="type-app-title text-xl sm:text-2xl">Settings</h1>
      <p className="type-chat-body mt-2 text-slate-600">{appConfig.settingsSubtitle}</p>

      <section className="card mt-5 space-y-4 p-6 sm:p-7">
        <div>
          <h2 className="text-[15px] font-semibold text-cloudera-navy">AI Model</h2>
          <p className="type-chat-meta mt-1 text-slate-500">{appConfig.settingsModelHelper}</p>
        </div>

        {loading && (
          <p className="type-chat-body text-slate-500" role="status">
            Loading models…
          </p>
        )}

        {!loading && error && (
          <div className="space-y-3 rounded-xl border border-rose-100 bg-rose-50/80 px-4 py-3">
            <p className="type-chat-body text-rose-900">Unable to load available models.</p>
            <button type="button" onClick={retryLoad} className="btn-secondary py-2 text-xs">
              Retry
            </button>
          </div>
        )}

        {!loading && !error && models.length > 0 && !hasAvailableModel && (
          <p className="type-chat-body text-slate-600">No AI models are currently available.</p>
        )}

        {!loading && !error && models.length > 0 && (
          <>
            <div className="space-y-2">
              <label className="sr-only" htmlFor="settings-ai-model">
                AI Model
              </label>
              <select
                id="settings-ai-model"
                aria-label="AI Model"
                disabled={!hasAvailableModel}
                className="input"
                value={hasAvailableModel ? draftValue : ''}
                onChange={event => setDraftValue(event.target.value)}
              >
                {!hasAvailableModel && <option value="">No models available</option>}
                {hasAvailableModel && !draftValue && <option value="">Select a model</option>}
                <ModelOptions models={models} groupByProvider={groupByProvider} />
              </select>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="btn-primary px-4 py-2 text-sm"
                disabled={!canSave}
                onClick={saveModel}
              >
                Save model
              </button>
              {draftDirty && (
                <p className="type-chat-meta text-slate-500">Unsaved change — applies after Save.</p>
              )}
              {!draftDirty && committedValue && (
                <p className="type-chat-meta text-emerald-700">Saved for new chat messages.</p>
              )}
            </div>

            {selectedModel && (
              <div className="space-y-2 border-t border-slate-100 pt-4">
                {selectedModel.available ? (
                  <p className="type-chat-body flex items-center gap-2 text-emerald-700">
                    <span className="text-emerald-500" aria-hidden>
                      ●
                    </span>
                    Ready
                  </p>
                ) : (
                  <div className="type-chat-body space-y-1 text-slate-600">
                    <p className="flex items-center gap-2">
                      <span className="text-slate-400" aria-hidden>
                        ○
                      </span>
                      Unavailable
                    </p>
                    <p className="type-chat-meta pl-5 text-slate-500">
                      {friendlyUnavailableMessage(selectedModel.reason)}
                    </p>
                  </div>
                )}
                <p className="type-chat-meta text-slate-500">
                  Provider: {providerDisplayName(selectedModel.provider)}
                </p>
                <p className="type-chat-meta text-slate-400">{providerDeploymentHint(selectedModel.provider)}</p>
              </div>
            )}
          </>
        )}
      </section>
    </PageCenter>
  )
}
