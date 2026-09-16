export function BrandMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-9 w-9 place-items-center rounded-xl bg-cloudera-orange text-white shadow-sm">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.4">
          <path d="M4 7h16M7 12h10M10 17h4" strokeLinecap="round" />
        </svg>
      </div>
      <div>
        <div className="text-[15px] font-black tracking-[0.14em] text-cloudera-navy">CLOUDERA</div>
        <div className="text-[10px] font-semibold text-slate-400">BETTER DATA. BETTER AI.</div>
      </div>
    </div>
  )
}
