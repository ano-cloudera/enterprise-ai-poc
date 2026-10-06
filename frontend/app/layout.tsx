import type { ReactNode } from 'react'
import '../src/index.css'
import { AppShell } from '../src/layout/AppShell'
import { appConfig } from '../src/config/appConfig'
import { Providers } from './providers'

export const metadata = {
  title: appConfig.headerTitle,
  description: appConfig.emptyStateDescription,
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
