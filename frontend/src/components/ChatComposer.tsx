'use client'

import { FormEvent, KeyboardEvent, useEffect, useRef } from 'react'
import { ArrowUp, Square } from 'lucide-react'
import { appConfig } from '../config/appConfig'

const MAX_COMPOSER_HEIGHT = 200

type ChatComposerProps = {
  value: string
  loading: boolean
  disabled: boolean
  modelHint?: string | null
  onChange: (value: string) => void
  onSubmit: () => void
  onStop: () => void
}

export function ChatComposer({
  value,
  loading,
  disabled,
  modelHint,
  onChange,
  onSubmit,
  onStop,
}: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const next = Math.max(24, Math.min(el.scrollHeight, MAX_COMPOSER_HEIGHT))
    el.style.height = `${next}px`
  }, [value])

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && value.trim() && !loading && !disabled) {
      event.preventDefault()
      onSubmit()
    }
  }

  return (
    <form
      onSubmit={(event: FormEvent) => {
        event.preventDefault()
        onSubmit()
      }}
      className="w-full shrink-0 pb-2 pt-1"
    >
      <div className="flex min-h-[56px] w-full items-center gap-2 rounded-[18px] border border-slate-200/90 bg-white px-3 py-2 shadow-[0_2px_12px_rgba(36,19,95,0.07)]">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={disabled && !loading}
          onChange={event => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={appConfig.chatPlaceholder}
          className="scrollbar-hidden max-h-[200px] min-h-[24px] flex-1 resize-none bg-transparent py-1 text-[15px] leading-normal outline-none placeholder:text-[15px] placeholder:text-slate-400"
        />
        {loading ? (
          <button
            type="button"
            aria-label="Stop request"
            onClick={onStop}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cloudera-orange text-white transition-colors hover:bg-rose-600"
          >
            <Square size={13} fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            aria-label="Send question"
            disabled={disabled || !value.trim()}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cloudera-orange text-white disabled:opacity-40"
          >
            <ArrowUp size={16} />
          </button>
        )}
      </div>
      {modelHint && <p className="mt-1.5 px-1 text-[11px] text-amber-700">{modelHint}</p>}
    </form>
  )
}
