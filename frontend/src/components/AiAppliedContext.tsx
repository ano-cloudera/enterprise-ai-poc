import React from 'react'
import { RotateCcw, Undo2, X } from 'lucide-react'
import type { AppliedContextItem } from '../types/api'

export function AiAppliedContext({ items, onRemove, onReset, onUndo, canUndo = false }: {
  items: AppliedContextItem[]
  onRemove: (kind: AppliedContextItem['kind'], target: string) => void
  onReset: () => void
  onUndo?: () => void
  canUndo?: boolean
}) {
  if (!items.length) return null
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-2xl border border-orange-100 bg-white px-4 py-3 shadow-sm">
      <span className="text-[11px] font-extrabold uppercase tracking-[.12em] text-cloudera-navy">Applied by AI:</span>
      {items.map(item => (
        <span key={`${item.kind}-${item.target}`} className="inline-flex items-center gap-1.5 rounded-full border border-orange-100 bg-orange-50 px-3 py-1.5 text-xs font-bold capitalize text-cloudera-orange">
          {item.label}
          <button type="button" aria-label={`Remove ${item.label}`} onClick={() => onRemove(item.kind, item.target)} className="rounded-full p-0.5 hover:bg-orange-100"><X size={12} /></button>
        </span>
      ))}
      <span className="ml-auto flex items-center gap-3">
        {canUndo && onUndo && <button type="button" onClick={onUndo} className="inline-flex items-center gap-1.5 text-xs font-bold text-cloudera-violet hover:text-cloudera-navy"><Undo2 size={13} />Undo AI changes</button>}
        <button type="button" onClick={onReset} className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-cloudera-navy"><RotateCcw size={13} />Reset all</button>
      </span>
    </div>
  )
}
