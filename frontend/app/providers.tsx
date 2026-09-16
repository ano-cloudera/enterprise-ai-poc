'use client'

import type { ReactNode } from 'react'
import { ProjectProvider } from '../src/lib/project'
import { DashboardStateProvider } from '../src/lib/dashboardState'

export function Providers({ children }: { children: ReactNode }) {
  return <ProjectProvider><DashboardStateProvider>{children}</DashboardStateProvider></ProjectProvider>
}
