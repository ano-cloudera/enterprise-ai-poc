'use client'
import type { ReactNode } from 'react'
import { ModelSelectionProvider } from '../src/lib/modelSelection'
export function Providers({ children }: { children: ReactNode }) { return <ModelSelectionProvider>{children}</ModelSelectionProvider> }
