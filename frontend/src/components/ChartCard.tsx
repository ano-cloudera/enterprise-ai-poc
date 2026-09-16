import type { ReactNode } from 'react'

export function ChartCard({ title, subtitle, children, action }: { title: string; subtitle?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="card overflow-hidden">
      <div className="flex items-start justify-between px-5 pt-5">
        <div><h3 className="text-sm font-extrabold text-cloudera-navy">{title}</h3>{subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}</div>
        {action}
      </div>
      <div className="p-5 pt-3">{children}</div>
    </section>
  )
}
