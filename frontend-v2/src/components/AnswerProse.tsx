import { formatAnswerParagraphs } from '../lib/answerFormatting'

export function AnswerProse({
  text,
  omitTables = false,
  className = '',
  emphasis = false,
}: {
  text: string
  omitTables?: boolean
  className?: string
  emphasis?: boolean
}) {
  const paragraphs = formatAnswerParagraphs(text, { omitTables })
  if (!paragraphs.length) return null
  return (
    <div className={`space-y-3 ${className}`}>
      {paragraphs.map((paragraph, index) => (
        <p
          key={index}
          className={`whitespace-pre-wrap ${emphasis && index === 0 ? 'text-[17px] font-semibold leading-relaxed text-slate-900 sm:text-base' : 'type-chat-body'}`}
        >
          {paragraph.split('\n').map((line, lineIndex) => {
            const numbered = line.match(/^(\d+\.)\s+(.*)$/)
            if (numbered) {
              return (
                <span key={lineIndex} className="block pl-1">
                  <span className="font-semibold text-cloudera-navy">{numbered[1]}</span> {numbered[2]}
                </span>
              )
            }
            return (
              <span key={lineIndex} className="block">
                {line}
              </span>
            )
          })}
        </p>
      ))}
    </div>
  )
}
