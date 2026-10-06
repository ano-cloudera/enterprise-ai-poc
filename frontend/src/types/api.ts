export type ProviderName = 'qwen' | 'gemini' | 'openai'

export type ModelInfo = {
  provider: ProviderName
  id: string
  label: string
  available: boolean
  reason: string | null
}

export type ModelSelection = { provider: ProviderName; model: string }

export type ChartSpec = {
  type: 'bar' | 'line' | 'area' | 'scatter' | 'pie' | 'table' | 'kpi'
  title: string
  x?: string | null
  y?: string | null
  series?: string | null
}

export type AnalysisOutput = {
  direct_answer: string
  executive_summary: string
  insights: string[]
  business_implications: string[]
  caveats: string[]
  data_reference: string
  chart_spec: ChartSpec | null
}

export type ChatResponse = {
  request_id: string
  session_id: string
  status: 'SUCCESS' | 'CLARIFICATION' | 'NO_DATA' | 'UNSUPPORTED' | 'ERROR'
  provider: ProviderName
  model: string
  strategy:
    | 'governed'
    | 'sql_fallback'
    | 'clarification'
    | 'unsupported'
    | 'conversational'
    | 'exploratory_local'
    | 'local_agent_exploratory'
    | 'error'
  answer: AnalysisOutput
  data: { columns: string[]; rows: Record<string, unknown>[]; row_count: number; execution_ms: number }
  chart_spec: ChartSpec | null
  timings: {
    context_ms?: number
    planning_ms?: number
    validation_ms?: number
    agent_ms?: number
    query_ms?: number
    analysis_ms?: number
    total_ms: number
  }
  retry_count: number
}

export type SuggestedQuestion = {
  id: string
  question: string
  domain: string
  domains: string[]
  difficulty: 'simple' | 'medium' | 'complex'
  analysis_type: string
  expected_visualization: string
}
