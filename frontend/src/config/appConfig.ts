/** Branding and copy — override via NEXT_PUBLIC_* env vars for reuse across deployments. */
function env(key: string, fallback: string): string {
  const value = process.env[key]?.trim()
  return value || fallback
}

export const appConfig = {
  appName: env('NEXT_PUBLIC_APP_NAME', 'Cloudera Data Intelligence'),
  customerName: env('NEXT_PUBLIC_CUSTOMER_NAME', ''),
  assistantName: env('NEXT_PUBLIC_ASSISTANT_NAME', 'Assistant'),
  get headerTitle(): string {
    return [this.customerName, this.appName].filter(Boolean).join(' ') || this.appName
  },
  get sidebarProductName(): string {
    return this.customerName || this.appName
  },
  sidebarTagline: env('NEXT_PUBLIC_APP_TAGLINE', 'AI Workspace'),
  chatPlaceholder: env('NEXT_PUBLIC_CHAT_PLACEHOLDER', 'Ask a question about your data…'),
  emptyStateTitle: env('NEXT_PUBLIC_EMPTY_STATE_TITLE', 'Ask your data a question'),
  emptyStateDescription: env(
    'NEXT_PUBLIC_EMPTY_STATE_DESCRIPTION',
    'Get a grounded answer, governed metrics, and a relevant visualization.',
  ),
  settingsSubtitle: 'Choose the AI model used for new conversations.',
  settingsModelHelper: 'Select the model you want this assistant to use.',
  navigationAskData: env('NEXT_PUBLIC_NAV_ASK_DATA', 'Ask Data'),
  navigationSettings: env('NEXT_PUBLIC_NAV_SETTINGS', 'Settings'),
  branding: {
    /** Served from `public/` (default: repo `assets/Logo.png` copied to public/Logo.png). */
    logo: env('NEXT_PUBLIC_APP_LOGO', '/Logo.png'),
    emptyStateLogo: env('NEXT_PUBLIC_EMPTY_STATE_LOGO', '/Logo.png'),
  },
} as const
