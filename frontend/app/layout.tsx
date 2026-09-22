import type { ReactNode } from 'react'
import { Plus_Jakarta_Sans } from 'next/font/google'
import '../src/index.css'
import { Providers } from './providers'
import { AppShell } from '../src/layout/AppShell'

// A distinct, warm-geometric sans instead of the near-universal AI-tool
// default (Inter) - chosen so the product reads as its own thing rather
// than a template. Self-hosted via next/font, no external request.
const bodyFont = Plus_Jakarta_Sans({ subsets: ['latin'], weight: ['400', '500', '600', '700', '800'], variable: '--font-body' })

export const metadata = {
  title: 'Enterprise AI PoC',
  description: 'Reusable Cloudera AI enterprise PoC foundation',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en" className={bodyFont.variable}><body><Providers><AppShell>{children}</AppShell></Providers></body></html>
}
