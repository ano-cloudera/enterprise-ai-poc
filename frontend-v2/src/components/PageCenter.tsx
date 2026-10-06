import type { ReactNode } from 'react'

/** Centered non-chat pages (Settings, etc.) — narrower than conversation grid. */
export function pageCenterClassName(extra?: string): string {
  const base = 'mx-auto w-full max-w-[820px] px-6 py-6'
  return extra ? `${base} ${extra}` : base
}

export function PageCenter({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={pageCenterClassName(className)}>{children}</div>
}
