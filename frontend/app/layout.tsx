import type { ReactNode } from 'react'
import '../src/index.css'
import { Providers } from './providers'
import { AppShell } from '../src/layout/AppShell'

export const metadata = {
  title: 'Enterprise AI PoC',
  description: 'Reusable Cloudera AI enterprise PoC foundation',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>
}
