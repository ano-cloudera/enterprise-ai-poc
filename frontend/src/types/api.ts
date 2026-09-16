export type DashboardState = {
  filters: Record<string, string[]>
  date_range: { preset: string | null; start: string | null; end: string | null }
  metric: string
  dimension: string
  highlights: { target: string; value: string }[]
  ai_applied_context: AppliedContextItem[]
  revision: number
  chat: {
    chart: { chart_type: Exclude<ChartSpec['type'], 'none'>; dimension: string; metric: string } | null
    table: { visible: boolean; columns: string[] }
  }
}

export type AppliedContextItem = { kind: 'filter' | 'date_range'; target: string; label: string }

export type ChartSpec = {
  type: 'line' | 'bar' | 'area' | 'pie' | 'table' | 'none'
  title: string
  x: string[]
  series: { name: string; data: (number | string | null)[] }[]
  x_label?: string | null
  y_label?: string | null
  dimension?: string | null
  metric?: string | null
  target?: 'chat' | 'dashboard' | 'both'
}

export type UIActionType =
  | 'SET_FILTER'
  | 'SET_DATE_RANGE'
  | 'CHANGE_METRIC'
  | 'CHANGE_DIMENSION'
  | 'RENDER_CHART'
  | 'SHOW_TABLE'
  | 'HIGHLIGHT_CARD'
  | 'RESET_FILTER'

export type UIAction =
  | { type: 'SET_FILTER'; target: string; value: string[] }
  | { type: 'SET_DATE_RANGE'; value: string | { start: string; end: string } }
  | { type: 'CHANGE_METRIC'; value: string }
  | { type: 'CHANGE_DIMENSION'; value: string }
  | { type: 'RENDER_CHART'; target: 'chat' | 'dashboard' | 'both'; value: { chart_type: Exclude<ChartSpec['type'], 'none'>; dimension: string; metric: string } }
  | { type: 'SHOW_TABLE'; target: 'chat' | 'dashboard' | 'both'; value: { columns: string[] } }
  | { type: 'HIGHLIGHT_CARD'; target: string; value: string | string[] }
  | { type: 'RESET_FILTER'; target?: string }

export type ChatResponse = {
  status: 'ok' | 'fallback' | 'error'
  question: string
  answer: {
    summary: string
    drivers: string[]
    recommended_actions: string[]
    caveats: string[]
  }
  data: {
    columns: string[]
    rows: Record<string, unknown>[]
  }
  chart_spec: ChartSpec | null
  ui_actions: UIAction[]
  metadata: {
    trace_id: string
    session_id: string
    intent: string
    resolved_context: DashboardState
    execution_time_ms: number
  }
}

export type DashboardOverview = {
  period: string
  kpis: { key: string; label: string; value: number | string; format: string; delta: number | null }[]
  sales_trend: { month: string; sales: number }[]
  region_sales: { region: string; sales: number }[]
  top_products: { product: string; category: string; sales: number }[]
  channel_share: { channel: string; sales: number; share: number }[]
  ai_insight: { headline: string; summary: string; actions: string[] }
  refreshed_at?: string
  forecast?: { value: number; format: string; period: string; delta?: number | null }
  market_signals?: {
    opportunity_score?: number
    opportunity_context?: string
    market_growth?: number
    competitive_pressure?: number
    distribution_gap?: number
    weather_correlation?: number
  }
}
