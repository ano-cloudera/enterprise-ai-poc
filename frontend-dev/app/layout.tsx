import type { ReactNode } from 'react'
import { Plus_Jakarta_Sans } from 'next/font/google'
import '../src/index.css'
import { AppShell } from '../src/layout/AppShell'
import { appConfig } from '../src/config/appConfig'
import { Providers } from './providers'

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
})

export const metadata = {
  title: appConfig.headerTitle,
  description: appConfig.emptyStateDescription,
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={plusJakarta.variable}>
      <body className={plusJakarta.className}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
