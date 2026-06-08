import { FRIENDS_LOGO_DOTS } from '@/theme/friends'

type TitleSize = 'xs' | 'sm' | 'md' | 'lg'
type TitleVariant = 'light' | 'dark'

const SIZE_CLASSES: Record<TitleSize, { text: string; dot: string; gap: string }> = {
  xs: { text: 'text-[7px]', dot: 'w-0.5 h-0.5', gap: 'gap-px' },
  sm: { text: 'text-[9px]', dot: 'w-1 h-1', gap: 'gap-0.5' },
  md: { text: 'text-xs', dot: 'w-1 h-1', gap: 'gap-0.5' },
  lg: { text: 'text-sm', dot: 'w-1.5 h-1.5', gap: 'gap-0.5' },
}

function FriendsStyleLine({
  letters,
  size,
  variant,
  dotOffset = 0,
  className = '',
}: {
  letters: string[]
  size: TitleSize
  variant: TitleVariant
  dotOffset?: number
  className?: string
}) {
  const s = SIZE_CLASSES[size]
  const letterClass = variant === 'light' ? 'text-white' : 'text-paper-900'

  return (
    <div className={`inline-flex items-center ${s.gap} font-black tracking-tight ${s.text} ${letterClass} ${className}`}>
      {letters.map((letter, i) => (
        <span key={`${letter}-${i}`} className={`inline-flex items-center ${s.gap}`}>
          <span className="leading-none">{letter}</span>
          {i < letters.length - 1 && (
            <span
              className={`${s.dot} rounded-full shrink-0`}
              style={{ backgroundColor: FRIENDS_LOGO_DOTS[(i + dotOffset) % FRIENDS_LOGO_DOTS.length] }}
              aria-hidden
            />
          )}
        </span>
      ))}
    </div>
  )
}

/** C·E·N·T·R·A·L / P·E·R·K — Friends title-card style */
export function CentralPerkFriendsTitle({
  size = 'md',
  variant = 'light',
  className = '',
}: {
  size?: TitleSize
  variant?: TitleVariant
  className?: string
}) {
  return (
    <div
      className={`flex flex-col items-center leading-none ${className}`}
      aria-label="Central Perk"
    >
      <FriendsStyleLine letters={['C', 'E', 'N', 'T', 'R', 'A', 'L']} size={size} variant={variant} dotOffset={0} />
      <FriendsStyleLine letters={['P', 'E', 'R', 'K']} size={size} variant={variant} dotOffset={2} className="mt-0.5" />
    </div>
  )
}

/** Classic F·R·I·E·N·D·S title with colored dots */
export function FriendsLogo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const letters = ['F', 'R', 'I', 'E', 'N', 'D', 'S']
  const mapped: TitleSize = size === 'lg' ? 'lg' : size === 'sm' ? 'sm' : 'md'

  return (
    <FriendsStyleLine letters={letters} size={mapped} variant="dark" />
  )
}

/** iOS-style purple gradient wallpaper strip (Pinterest homescreen pins) */
export function FriendsWallpaperStrip() {
  return (
    <div
      className="rounded-3xl p-4 shadow-card-lg border border-friends-purple-light/30"
      style={{
        background: 'linear-gradient(145deg, #6B3FA0 0%, #4A2870 45%, #9B6BC4 100%)',
      }}
    >
      <FriendsLogo size="lg" />
      <p className="text-white/75 text-xs mt-2 italic">The one with your second brain</p>
    </div>
  )
}
