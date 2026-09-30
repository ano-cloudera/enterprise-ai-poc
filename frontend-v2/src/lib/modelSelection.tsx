'use client'

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'
import type { ModelInfo, ModelSelection } from '../types/api'


const STORAGE_KEY = 'tempo-scan-v2.model-selection'

type Value = {
  models: ModelInfo[]
  selection: ModelSelection | null
  loading: boolean
  error: string
  select: (selection: ModelSelection) => void
}

const Context = createContext<Value | null>(null)


export function ModelSelectionProvider({ children }: { children: ReactNode }) {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [selection, setSelection] = useState<ModelSelection | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.models().then(({ models: discovered }) => {
      setModels(discovered)
      let saved: ModelSelection | null = null
      try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') } catch { saved = null }
      const available = discovered.filter(model => model.available)
      const selected = available.find(model => model.provider === saved?.provider && model.id === saved?.model) || available[0]
      setSelection(selected ? { provider: selected.provider, model: selected.id } : null)
    }).catch(() => setError('Unable to discover configured AI models.')).finally(() => setLoading(false))
  }, [])

  function select(next: ModelSelection) {
    const allowed = models.some(model => model.available && model.provider === next.provider && model.id === next.model)
    if (!allowed) return
    setSelection(next)
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* optional browser persistence */ }
  }

  const value = useMemo(() => ({ models, selection, loading, error, select }), [models, selection, loading, error])
  return <Context.Provider value={value}>{children}</Context.Provider>
}


export function useModelSelection() {
  const value = useContext(Context)
  if (!value) throw new Error('useModelSelection must be used inside ModelSelectionProvider')
  return value
}
