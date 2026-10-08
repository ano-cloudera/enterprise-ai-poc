'use client'

import { Bot } from 'lucide-react'
import { useState } from 'react'
import { appConfig } from '../config/appConfig'

export function BrandMark() {
  const [failed, setFailed] = useState(false)
  const src = appConfig.branding.logo.trim()

  return (
    <div className="flex min-w-0 items-center gap-2.5">
      {!src || failed ? (
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-cloudera-navy">
          <Bot size={20} strokeWidth={1.5} aria-hidden />
        </div>
      ) : (
        <img
          src={src}
          alt=""
          aria-hidden
          className="h-9 w-9 shrink-0 rounded-lg object-contain shadow-sm"
          onError={() => setFailed(true)}
        />
      )}
      <div className="min-w-0 text-left leading-tight">
        <div className="text-[15px] font-semibold leading-snug text-cloudera-navy">{appConfig.sidebarBrandTitle}</div>
        <div className="truncate text-xs text-slate-500">{appConfig.sidebarTagline}</div>
      </div>
    </div>
  )
}
