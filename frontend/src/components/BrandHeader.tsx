interface Props {
  compact?: boolean
  onLogoClick?: () => void
}

export function VoidWordmark({ className = 'h-7 w-[168px]' }: { className?: string }) {
  return (
    <svg viewBox="0 0 220 36" className={`void-brand-svg ${className}`} role="img" aria-label="THE VOID">
      <text
        x="110"
        y="27"
        textAnchor="middle"
        fill="none"
        stroke="currentColor"
        strokeWidth="0.85"
        fontFamily="Cinzel, Georgia, serif"
        fontSize="26"
        fontWeight="500"
        letterSpacing="3.2"
      >
        THE VOID
      </text>
    </svg>
  )
}

export function BrandHeader({ compact = false, onLogoClick }: Props) {
  const word = <VoidWordmark className={compact ? 'h-6 w-[140px]' : 'h-8 w-[190px]'} />

  if (!onLogoClick) return word

  return (
    <button
      type="button"
      onClick={onLogoClick}
      className="rounded-xl transition active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-void-red"
      aria-label="Start new chat"
      title="New chat"
    >
      {word}
    </button>
  )
}
