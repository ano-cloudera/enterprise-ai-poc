import { Info } from 'lucide-react'

type DataNoteProps = {
  note: string | null
  sources: string[]
}

export function DataNote({ note, sources }: DataNoteProps) {
  if (!note && sources.length === 0) return null

  return (
    <div className="answer-footnote answer-footnote-panel space-y-2" aria-label="Data note">
      {note && (
        <p className="type-chat-meta flex gap-2 leading-relaxed text-slate-500">
          <Info size={13} className="mt-0.5 shrink-0 text-slate-400" aria-hidden />
          <span className="min-w-0">
            <span className="font-semibold text-slate-500">Data note. </span>
            {note}
          </span>
        </p>
      )}
      {sources.length > 0 && (
        <div className={note ? 'pl-5' : ''}>
          <div className="type-chat-meta mb-1 text-slate-400">{sources.length > 1 ? 'Sources' : 'Source'}</div>
          <ul className="flex flex-wrap gap-1.5">
            {sources.map(source => (
              <li key={source}>
                <code className="type-chat-meta inline-block max-w-full break-all rounded-md border border-slate-200/80 bg-white px-2 py-0.5 font-mono text-[11px] text-slate-600">
                  {source}
                </code>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
