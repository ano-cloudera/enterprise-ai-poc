/** Branding and copy — override via NEXT_PUBLIC_* env vars for reuse across deployments. */
function env(key: string, fallback: string): string {
  const value = process.env[key]?.trim()
  return value || fallback
}

export const appConfig = {
  appName: env('NEXT_PUBLIC_APP_NAME', 'Scan Intelligence'),
  customerName: env('NEXT_PUBLIC_CUSTOMER_NAME', ''),
  assistantName: env('NEXT_PUBLIC_ASSISTANT_NAME', 'Assistant'),
  get headerTitle(): string {
    return [this.customerName, this.appName].filter(Boolean).join(' ') || this.appName
  },
  /** Primary line in sidebar header (logo row). */
  get sidebarBrandTitle(): string {
    return this.customerName || this.appName
  },
  sidebarTagline: env('NEXT_PUBLIC_APP_TAGLINE', 'AI Workspace'),
  sidebarPoweredByLabel: env('NEXT_PUBLIC_SIDEBAR_POWERED_BY', 'Powered by Cloudera'),
  sidebarFooterCaption: env(
    'NEXT_PUBLIC_SIDEBAR_FOOTER_CAPTION',
    'Tempo Scan proof of concept',
  ),
  starterQuestionsCaption: env('NEXT_PUBLIC_STARTER_QUESTIONS_CAPTION', 'Start with a question'),
  chatPlaceholder: env('NEXT_PUBLIC_CHAT_PLACEHOLDER', 'Ask a question about your data…'),
  emptyStateTitle: env('NEXT_PUBLIC_EMPTY_STATE_TITLE', 'Ask your data a question'),
  emptyStateDescription: env(
    'NEXT_PUBLIC_EMPTY_STATE_DESCRIPTION',
    'Get a grounded answer, governed metrics, and a relevant visualization.',
  ),
  settingsSubtitle: 'Choose the AI model used for new conversations.',
  settingsModelHelper: 'Select the model you want this assistant to use.',
  navigationAskData: env('NEXT_PUBLIC_NAV_ASK_DATA', 'Ask Data'),
  navigationUsage: env('NEXT_PUBLIC_NAV_USAGE', 'Usage'),
  navigationSettings: env('NEXT_PUBLIC_NAV_SETTINGS', 'Settings'),
  branding: {
    /** Served from `public/` (default: repo `assets/Logo.png` copied to public/Logo.png). */
    logo: env('NEXT_PUBLIC_APP_LOGO', '/Logo.png'),
    emptyStateLogo: env('NEXT_PUBLIC_EMPTY_STATE_LOGO', '/Logo.png'),
  },
  /** Genie-style split report panel (frontend-dev). */
  analysisReportPanel: env('NEXT_PUBLIC_ANALYSIS_REPORT_PANEL', 'true') !== 'false',
  reportDocumentLabel: env('NEXT_PUBLIC_REPORT_DOCUMENT_LABEL', 'Analysis Workspace'),
  reportWorkspaceSubtitle: env(
    'NEXT_PUBLIC_REPORT_WORKSPACE_SUBTITLE',
    'Analisis dari percakapan ini',
  ),
  reportDatabaseStatusLabel: env('NEXT_PUBLIC_REPORT_DB_STATUS', 'Database connected'),
  /** When set, Query tab shows “View lineage” linking with `?table=` source. */
  viewLineageBaseUrl: env('NEXT_PUBLIC_LINEAGE_VIEW_URL', ''),
} as const
