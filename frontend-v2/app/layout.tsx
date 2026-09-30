import type { ReactNode } from 'react'
import '../src/index.css'
import { AppShell } from '../src/layout/AppShell'
import { Providers } from './providers'
export const metadata = { title: 'TEMPO Scan V2', description: 'TEMPO Commercial Intelligence Ask Data' }
export default function RootLayout({ children }: { children: ReactNode }) { return <html lang="id"><body><Providers><AppShell>{children}</AppShell></Providers></body></html> }
