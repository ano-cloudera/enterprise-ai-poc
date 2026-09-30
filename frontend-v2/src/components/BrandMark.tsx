export function BrandMark() {
  return (
    <div className="flex items-center gap-3">
      <img src="/cloudera-logo.png" alt="Cloudera" className="h-11 w-11 shrink-0 rounded-xl shadow-sm" />
      <div>
        <div className="text-lg font-black tracking-[0.14em] text-cloudera-navy">CLOUDERA</div>
        <div className="text-xs font-semibold text-slate-400">BETTER DATA. BETTER AI.</div>
      </div>
    </div>
  )
}
