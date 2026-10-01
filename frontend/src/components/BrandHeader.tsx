import { Brain } from 'lucide-react'

interface Props {
  compact?: boolean
  onLogoClick?: () => void
}

export function BrandHeader({ compact = false, onLogoClick }: Props) {
  const inner = (
    <div className={`flex items-center gap-2.5 ${compact ? '' : 'flex-col text-center'}`}>
      <div
        className={`rounded-xl bg-paper-800 text-paper-50 flex items-center justify-center shrink-0 ${
          compact ? 'w-8 h-8' : 'w-10 h-10'
        }`}
      >
        <Brain size={compact ? 16 : 20} strokeWidth={1.75} />
      </div>
      <div className={compact ? 'min-w-0 text-left' : ''}>
        <p className={`font-semibold tracking-tight text-paper-800 ${compact ? 'text-sm' : 'text-base'}`}>
          Second Brain
        </p>
        {!compact && (
          <p className="text-[10px] text-paper-400 mt-0.5">One vault · today’s daily note</p>
        )}
      </div>
    </div>
  )

  if (!onLogoClick) return inner

  return (
    <button
      type="button"
      onClick={onLogoClick}
      className="rounded-xl transition active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-paper-300"
      aria-label="Start new chat"
      title="New chat"
    >
      {inner}
    </button>
  )
}
