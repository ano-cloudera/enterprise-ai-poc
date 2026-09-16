import type { ReactNode } from 'react'

type PageIntroProps = {
  title: string
  subtitle: string
  action?: ReactNode
}

export function PageIntro({ title, subtitle, action }: PageIntroProps) {
  return (
    <section aria-label="Page introduction" className="mb-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 max-w-4xl">
          <h1 className="text-[26px] font-black leading-tight tracking-[-0.025em] text-cloudera-navy sm:text-[28px]">{title}</h1>
          <p className="mt-1 max-w-3xl text-sm leading-5 text-slate-500">{subtitle}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </section>
  )
}
