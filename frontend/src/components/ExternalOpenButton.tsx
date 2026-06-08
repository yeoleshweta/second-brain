import { ExternalLink } from 'lucide-react'
import { openExternalUrl } from '@/lib/openExternal'

interface Props {
  url: string
  label: string
  hint?: string
  className?: string
  variant?: 'primary' | 'secondary'
}

export function ExternalOpenButton({
  url,
  label,
  hint,
  className = '',
  variant = 'secondary',
}: Props) {
  const base =
    'flex items-center justify-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg min-h-[44px] transition touch-manipulation w-full sm:w-auto'
  const styles =
    variant === 'primary'
      ? 'bg-friends-sofa text-white active:bg-friends-sofa-dark shadow-card'
      : 'text-paper-600 active:text-accent-500 bg-paper-100 active:bg-paper-200'

  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => openExternalUrl(url)}
        className={`${base} ${styles}`}
      >
        <ExternalLink size={14} />
        {label}
      </button>
      {hint && <p className="text-[10px] text-paper-400 mt-1.5 leading-snug">{hint}</p>}
    </div>
  )
}
