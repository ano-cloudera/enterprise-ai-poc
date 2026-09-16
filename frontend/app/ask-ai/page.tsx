import { Suspense } from 'react'
import { AskAIPage } from '../../src/views/AskAIPage'
export default function Page() {
  return <Suspense fallback={<div className="card-pad text-sm text-slate-500">Loading Ask AI…</div>}><AskAIPage /></Suspense>
}
