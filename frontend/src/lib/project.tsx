'use client'

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'

type ProjectConfig = {
  project_id: string
  project_name: string
  project_subtitle: string
  brand: Record<string, string>
  model_name: string
  data_backend: string
  semantic_execution_mode: string
  semantic_capabilities_enabled: boolean
  guardrails_enabled: boolean
}

const fallback: ProjectConfig = {
  project_id: 'tempo_scan',
  project_name: 'Tempo Scan Commercial Intelligence Assistant',
  project_subtitle: 'Trusted data to executive insight, powered by Cloudera AI',
  brand: {},
  model_name: 'Qwen3.8-27B-AWQ',
  data_backend: 'duckdb',
  semantic_execution_mode: 'legacy',
  semantic_capabilities_enabled: false,
  guardrails_enabled: false,
}

const ProjectContext = createContext<{ config: ProjectConfig; loading: boolean }>({ config: fallback, loading: false })

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<ProjectConfig>(fallback)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.publicConfig().then((value) => {
      setConfig({ ...fallback, ...value })
      const brand = value.brand || {}
      if (brand.primary) document.documentElement.style.setProperty('--project-primary', brand.primary)
      if (brand.secondary) document.documentElement.style.setProperty('--project-secondary', brand.secondary)
    }).catch(() => setConfig(fallback)).finally(() => setLoading(false))
  }, [])

  const value = useMemo(() => ({ config, loading }), [config, loading])
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
}

export function useProject() { return useContext(ProjectContext) }
